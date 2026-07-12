import type { APIContext } from 'astro';

export const prerender = false;

/**
 * GitHub Webhook 端点
 * 接收 GitHub push 事件,触发服务器自动构建和部署
 * 配置: 在 GitHub 仓库 Settings > Webhooks 中添加
 *   - Payload URL: https://snhgn.me/api/webhook
 *   - Content type: application/json
 *   - Secret: 与 WEBHOOK_SECRET 环境变量一致
 *   - Events: Just the push event
 */
export async function POST(context: APIContext) {
  const { request, env } = context;

  // 1. 验证 Webhook Secret
  const webhookSecret = env.WEBHOOK_SECRET;
  if (!webhookSecret) {
    return new Response(JSON.stringify({ error: 'WEBHOOK_SECRET not configured' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const signature = request.headers.get('x-hub-signature-256');
  if (!signature) {
    return new Response(JSON.stringify({ error: 'Missing signature' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const body = await request.text();

  // 2. 验证签名 (HMAC SHA-256)
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(webhookSecret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const expectedSig = await crypto.subtle.sign('HMAC', key, encoder.encode(body));
  const expectedSigHex = 'sha256=' + Array.from(new Uint8Array(expectedSig))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');

  if (signature !== expectedSigHex) {
    return new Response(JSON.stringify({ error: 'Invalid signature' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // 3. 检查事件类型
  const event = request.headers.get('x-github-event');
  if (event !== 'push') {
    return new Response(JSON.stringify({ message: `Ignored event: ${event}` }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // 4. 解析 payload
  const payload = JSON.parse(body);
  const ref = payload.ref as string;
  const branch = ref?.replace('refs/heads/', '');

  // 只处理 main 分支
  if (branch !== 'main') {
    return new Response(JSON.stringify({ message: `Ignored branch: ${branch}` }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // 5. 触发构建 (异步,不阻塞响应)
  const buildScript = env.BUILD_SCRIPT || '/home/a/build.sh';
  try {
    // 使用 spawn 异步执行构建脚本
    const { spawn } = await import('child_process');
    const child = spawn(buildScript, [], {
      detached: true,
      stdio: 'ignore',
      env: { ...process.env, GIT_PULL: '1' },
    });
    child.unref();
  } catch (err) {
    console.error('Failed to trigger build:', err);
  }

  return new Response(JSON.stringify({
    message: 'Build triggered',
    branch,
    commit: payload.after?.slice(0, 7),
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function GET() {
  return new Response(JSON.stringify({ status: 'webhook endpoint active' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
