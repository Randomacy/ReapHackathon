import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

type Product = {
  id: string;
  name: string;
  merchant?: { name?: string };
  available: boolean;
  priceRange?: {
    min?: { amount: number; currency: string };
    max?: { amount: number; currency: string };
  };
  previewVariant?: {
    id: string;
    name: string;
    available: boolean;
    price?: { amount: number; currency: string };
  };
};

type SearchResponse = {
  products?: Product[];
  pagination?: { returnedCount?: number; hasNextPage?: boolean; nextCursor?: string | null };
  warnings?: string[];
  error?: { code?: string; message?: string };
};

type SearchRequest = {
  query: string;
  context: { country: "SG"; currency: "SGD" };
  filters: { availability: "AVAILABLE_ONLY" };
  pagination: { limit: number; cursor?: string };
};

function readEnvValue(contents: string, name: string): string | undefined {
  const match = contents.match(new RegExp(`^${name}=(.*)$`, "m"));
  return match?.[1]?.trim().replace(/^['"]|['"]$/g, "");
}

async function main(): Promise<void> {
  const query = process.argv.slice(2).join(" ") || "Dutch Colony coffee";
  const env = await readFile(resolve(process.cwd(), ".env"), "utf8");
  const apiKey = readEnvValue(env, "REAP_API_KEY");

  if (!apiKey) {
    throw new Error("REAP_API_KEY is missing from .env");
  }

  const products: Product[] = [];
  let cursor: string | undefined;
  let page = 0;

  do {
    page += 1;
    const payload: SearchRequest = {
      query,
      context: { country: "SG", currency: "SGD" },
      filters: { availability: "AVAILABLE_ONLY" },
      pagination: { limit: 50, ...(cursor ? { cursor } : {}) },
    };

    const response = await fetch(
      "https://sg.sandbox.api.reap.global/agentic/products/search",
      {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "Reap-Version": "2025-02-14",
      },
        body: JSON.stringify(payload),
      },
    );

    const body = (await response.json()) as SearchResponse;
    if (!response.ok) {
      throw new Error(`${response.status} ${body.error?.code ?? "REQUEST_FAILED"}: ${body.error?.message ?? "Unknown error"}`);
    }

    products.push(...(body.products ?? []));
    cursor = body.pagination?.nextCursor ?? undefined;
    if (body.warnings?.length) console.log(`Page ${page} warnings:`, body.warnings);
  } while (cursor);

  console.log(`Query: ${query}`);
  console.log(`Results: ${products.length} across ${page} page${page === 1 ? "" : "s"}`);

  console.table(
    products.map((product) => ({
      merchant: product.merchant?.name ?? "(unknown)",
      product: product.name,
      available: product.available,
      min: product.priceRange?.min
        ? `${product.priceRange.min.currency} ${product.priceRange.min.amount}`
        : "",
      max: product.priceRange?.max
        ? `${product.priceRange.max.currency} ${product.priceRange.max.amount}`
        : "",
      variant: product.previewVariant?.name ?? "",
      variantId: product.previewVariant?.id ?? "",
      productId: product.id,
    })),
  );

}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
