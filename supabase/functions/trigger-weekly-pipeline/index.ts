import { triggerPipeline } from "../_shared/pipeline.ts";

Deno.serve(() => triggerPipeline("weekly"));
