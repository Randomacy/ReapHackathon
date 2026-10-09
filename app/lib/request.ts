type ApiResult = { error?: string };

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body = (await response.json()) as T & ApiResult;
  if (!response.ok) throw new Error(body.error ?? "Request failed.");
  return body;
}
