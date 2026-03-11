import { proxyAgentRequest } from "@/lib/agentProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function handle(request, context) {
  const params = await Promise.resolve(context?.params);
  return proxyAgentRequest(request, params?.path ?? []);
}

export const GET = handle;
export const POST = handle;
export const DELETE = handle;
export const OPTIONS = handle;
