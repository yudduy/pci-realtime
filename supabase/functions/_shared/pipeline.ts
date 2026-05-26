type PipelineKind = "weekly" | "daily_refresh";

function jsonResponse(payload: Record<string, unknown>, status: number): Response {
  return Response.json(payload, { status });
}

function isAuthorized(request: Request): boolean {
  const expected =
    Deno.env.get("PYTHON_PIPELINE_TRIGGER_SECRET") ??
    Deno.env.get("PYTHON_PIPELINE_WEBHOOK_SECRET") ??
    "";
  if (!expected) return false;
  return request.headers.get("x-pci-pipeline-secret") === expected;
}

export async function triggerPipeline(
  kind: PipelineKind,
  request: Request,
): Promise<Response> {
  if (!isAuthorized(request)) {
    return jsonResponse(
      {
        ok: false,
        error: "Unauthorized pipeline trigger.",
        run_type: kind,
      },
      401,
    );
  }

  const webhookUrl = Deno.env.get("PYTHON_PIPELINE_WEBHOOK_URL");
  const webhookSecret = Deno.env.get("PYTHON_PIPELINE_WEBHOOK_SECRET") ?? "";

  if (!webhookUrl) {
    return jsonResponse(
      {
        ok: false,
        error:
          "PYTHON_PIPELINE_WEBHOOK_URL is not configured; Edge Function is orchestration-only.",
        run_type: kind,
      },
      503,
    );
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-pci-pipeline-secret": webhookSecret,
    },
    body: JSON.stringify({
      run_type: kind,
      requested_at: new Date().toISOString(),
      source: "supabase_edge_function",
    }),
  });

  const text = await response.text();
  return jsonResponse(
    {
      ok: response.ok,
      run_type: kind,
      status: response.status,
      response: text,
    },
    response.ok ? 202 : 502,
  );
}
