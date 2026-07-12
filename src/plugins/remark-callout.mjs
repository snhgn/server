// src/plugins/remark-callout.mjs
// 支持 :::note / :::warning / :::tip / :::danger 容器语法
// 不依赖 unist-util-visit,手动遍历 tree

const CALLOUT_TYPES = ['note', 'warning', 'tip', 'danger'];

export default function remarkCallout() {
  return (tree) => {
    if (!tree || !tree.children) return;
    const newChildren = [];
    for (let i = 0; i < tree.children.length; i++) {
      const node = tree.children[i];
      // 检测 :::type 起始段落
      if (
        node.type === 'paragraph' &&
        node.children?.[0]?.type === 'text'
      ) {
        const match = node.children[0].value.match(/^:::(\w+)\s*$/);
        if (match && CALLOUT_TYPES.includes(match[1])) {
          const type = match[1];
          // 收集后续直到 ::: 的节点
          const content = [];
          let endIndex = i + 1;
          while (endIndex < tree.children.length) {
            const next = tree.children[endIndex];
            if (
              next.type === 'paragraph' &&
              next.children?.[0]?.type === 'text' &&
              /^:::\s*$/.test(next.children[0].value)
            ) {
              break;
            }
            content.push(next);
            endIndex++;
          }
          // 替换为 div 节点
          newChildren.push({
            type: 'div',
            data: { hName: 'div', hProperties: { className: ['callout', `callout--${type}`] } },
            children: [
              { type: 'paragraph', children: [{ type: 'text', value: type.toUpperCase() }] },
              ...content,
            ],
          });
          i = endIndex; // 跳过已消费的节点
          continue;
        }
      }
      newChildren.push(node);
    }
    tree.children = newChildren;
  };
}
