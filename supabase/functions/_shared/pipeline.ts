type PipelineKind = "weekly" | "daily_refresh";

export async function triggerPipeline(kind: PipelineKind): Promise<Response> {
  const webhookUrl = Deno.env.get("PYTHON_PIPELINE_WEBHOOK_URL");
  const webhookSecret = Deno.env.get("PYTHON_PIPELINE_WEBHOOK_SECRET") ?? "";

  if (!webhookUrl) {
    return Response.json(
      {
        ok: false,
        error:
          "PYTHON_PIPELINE_WEBHOOK_URL is not configured; Edge Function is orchestration-only.",
        run_type: kind,
      },
      { status: 503 },
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
  return Response.json(
    {
      ok: response.ok,
      run_type: kind,
      status: response.status,
      response: text,
    },
    { status: response.ok ? 202 : 502 },
  );
}
