import { triggerPipeline } from "../_shared/pipeline.ts";

Deno.serve((request) => triggerPipeline("weekly", request));
