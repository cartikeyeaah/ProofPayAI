import { httpApi } from "./client";
import { mockApi } from "./mock-api";

export const api = process.env.NEXT_PUBLIC_USE_MOCK === "false" ? httpApi : mockApi;
