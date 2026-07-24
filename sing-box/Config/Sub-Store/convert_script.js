  const scope = "SING-BOX-CONFIG";
  const source =
    typeof $content === "string" && $content.trim()
      ? $content
      : typeof $files !== "undefined" && Array.isArray($files)
        ? $files.find((file) => typeof file === "string" && file.trim())
        : undefined;

  if (!source) {
    throw new Error(`[${scope}] 没有读到模板内容`);
  }

  const parser =
    typeof ProxyUtils !== "undefined" && ProxyUtils.JSON5
      ? ProxyUtils.JSON5
      : JSON;

  let config;
  try {
    config = parser.parse(source.replace(/^\uFEFF/, ""));
  } catch (error) {
    throw new Error(`[${scope}] 模板不是有效的 JSON/JSON5: ${error.message}`);
  }

  if (!Array.isArray(config.outbounds)) {
    throw new Error(`[${scope}] 模板缺少 outbounds 数组`);
  }

  const placeholderPattern = /^\{([^{}]+)\}$/;
  const subscriptionNames = [];

  for (const outbound of config.outbounds) {
    if (!Array.isArray(outbound.outbounds)) continue;

    for (const item of outbound.outbounds) {
      if (typeof item !== "string") continue;
      const match = item.match(placeholderPattern);
      if (match && !subscriptionNames.includes(match[1])) {
        subscriptionNames.push(match[1]);
      }
    }
  }

  if (!subscriptionNames.length) {
    throw new Error(`[${scope}] 模板中没有找到 {订阅名} 占位符`);
  }

  const produced = await Promise.all(
    subscriptionNames.map(async (name) => {
      let outbounds;
      try {
        outbounds = await produceArtifact({
          type: "subscription",
          name,
          platform: "sing-box",
          produceType: "internal",
        });
      } catch (error) {
        throw new Error(
          `[${scope}] 读取订阅 "${name}" 失败: ${error.message}`,
        );
      }

      if (!Array.isArray(outbounds) || !outbounds.length) {
        throw new Error(`[${scope}] 订阅 "${name}" 没有可用节点`);
      }

      return [name, outbounds.map((outbound) => ({ ...outbound }))];
    }),
  );

  const templateTags = new Set(
    config.outbounds
      .map((outbound) => outbound && outbound.tag)
      .filter((tag) => typeof tag === "string" && tag),
  );
  const usedTags = new Set(templateTags);
  const subscriptionTags = new Map();
  const subscriptionNodes = [];

  function uniqueTag(tag, subscriptionName) {
    if (!usedTags.has(tag)) return tag;

    const qualified = `[${subscriptionName}] ${tag}`;
    if (!usedTags.has(qualified)) return qualified;

    let index = 2;
    while (usedTags.has(`${qualified} ${index}`)) index += 1;
    return `${qualified} ${index}`;
  }

  for (const [subscriptionName, nodes] of produced) {
    const renameMap = new Map();

    for (const node of nodes) {
      if (!node || typeof node !== "object") {
        throw new Error(`[${scope}] 订阅 "${subscriptionName}" 包含无效节点`);
      }
      if (typeof node.tag !== "string" || !node.tag.trim()) {
        throw new Error(
          `[${scope}] 订阅 "${subscriptionName}" 存在没有 tag 的节点`,
        );
      }

      const originalTag = node.tag;
      const tag = uniqueTag(originalTag, subscriptionName);
      renameMap.set(originalTag, tag);
      node.tag = tag;
      usedTags.add(tag);
    }

    for (const node of nodes) {
      if (typeof node.detour === "string" && renameMap.has(node.detour)) {
        node.detour = renameMap.get(node.detour);
      }
    }

    subscriptionTags.set(
      subscriptionName,
      nodes.map((node) => node.tag),
    );
    subscriptionNodes.push(...nodes);
  }

  function applyFilters(tags, filters, selectorTag) {
    if (!Array.isArray(filters) || !filters.length) return tags;

    let result = [...tags];
    for (const filter of filters) {
      const keywords = Array.isArray(filter.keywords) ? filter.keywords : [];
      const patterns = keywords.map((keyword) => {
        try {
          return new RegExp(keyword, "i");
        } catch (error) {
          throw new Error(
            `[${scope}] 策略组 "${selectorTag}" 的过滤正则无效: ${keyword}`,
          );
        }
      });

      if (!patterns.length) continue;
      if (filter.action === "include") {
        result = result.filter((tag) =>
          patterns.some((pattern) => pattern.test(tag)),
        );
      } else if (filter.action === "exclude") {
        result = result.filter(
          (tag) => !patterns.some((pattern) => pattern.test(tag)),
        );
      }
    }

    // Keep the selector valid when a region/filter has no matching nodes.
    return result.length ? result : tags;
  }

  const fixedOutbounds = [];
  const selectors = [];

  for (const outbound of config.outbounds) {
    if (outbound.type !== "selector") {
      fixedOutbounds.push(outbound);
      continue;
    }

    const expanded = [];
    for (const item of outbound.outbounds || []) {
      const match = typeof item === "string" && item.match(placeholderPattern);
      if (!match) {
        expanded.push(item);
        continue;
      }

      const tags = subscriptionTags.get(match[1]);
      if (!tags) {
        throw new Error(
          `[${scope}] 策略组 "${outbound.tag}" 引用了未知订阅 "${match[1]}"`,
        );
      }
      expanded.push(...applyFilters(tags, outbound.filter, outbound.tag));
    }

    outbound.outbounds = [...new Set(expanded)];
    delete outbound.filter;
    if (!outbound.outbounds.length) {
      throw new Error(`[${scope}] 策略组 "${outbound.tag}" 没有可用出站`);
    }
    selectors.push(outbound);
  }

  config.outbounds = [...fixedOutbounds, ...subscriptionNodes, ...selectors];

  const finalTags = new Set(config.outbounds.map((outbound) => outbound.tag));
  for (const selector of selectors) {
    const missing = selector.outbounds.filter((tag) => !finalTags.has(tag));
    if (missing.length) {
      throw new Error(
        `[${scope}] 策略组 "${selector.tag}" 引用了不存在的出站: ${missing.join(
          ", ",
        )}`,
      );
    }
  }

  console.log(
    `[${scope}] INFO: 已注入 ${subscriptionNodes.length} 个节点，来源: ${subscriptionNames.join(
      ", ",
    )}`,
  );
  $content = JSON.stringify(config, null, 2);
