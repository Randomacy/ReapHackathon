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

// Search terms for drinks that are normally prepared and sold by the cup.  A
// plain "coffee" search also returns retail bags, pods, and brewing equipment.
const SINGLE_CUP_COFFEE_QUERIES = [
  "coffee",
  "espresso",
  "americano",
  "latte",
  "cappuccino",
  "flat white",
  "mocha",
  "cold brew",
];

const NOT_A_SINGLE_CUP =
  /\b(bean|beans|ground|grounds|powder|capsule|capsules|pod|pods|drip bag|coffee bag|instant|bottle|bottled|can|canned|jar|box|bundle|pack|packet|subscription|machine|maker|filter|grinder|mug|tumbler|cup set)\b/i;

const SINGLE_CUP_DRINK =
  /\b(coffee|espresso|americano|latte|cappuccino|flat white|mocha|cold brew|cold drip|long black|macchiato|piccolo|cortado|affogato)\b/i;

function isSingleCupCoffee(product: Product): boolean {
  const text = `${product.name} ${product.previewVariant?.name ?? ""}`;
  return SINGLE_CUP_DRINK.test(text) && !NOT_A_SINGLE_CUP.test(text);
}

function readEnvValue(contents: string, name: string): string | undefined {
  const match = contents.match(new RegExp(`^${name}=(.*)$`, "m"));
  return match?.[1]?.trim().replace(/^['"]|['"]$/g, "");
}

async function main(): Promise<void> {
  const requestedQuery = process.argv.slice(2).join(" ").trim();
  const queries = requestedQuery ? [requestedQuery] : SINGLE_CUP_COFFEE_QUERIES;
  const env = await readFile(resolve(process.cwd(), ".env"), "utf8");
  const apiKey = readEnvValue(env, "REAP_API_KEY");

  if (!apiKey) {
    throw new Error("REAP_API_KEY is missing from .env");
  }

  const byId = new Map<string, Product>();
  let pageCount = 0;

  for (const query of queries) {
    let cursor: string | undefined;
    do {
      pageCount += 1;
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

      for (const product of body.products ?? []) byId.set(product.id, product);
      cursor = body.pagination?.nextCursor ?? undefined;
      if (body.warnings?.length) console.log(`Query "${query}" warnings:`, body.warnings);
    } while (cursor);
  }

  const products = [...byId.values()].filter(isSingleCupCoffee);
  console.log(`Searches: ${queries.join(", ")}`);
  console.log(`Single-cup coffees: ${products.length} (from ${byId.size} available matches across ${pageCount} page${pageCount === 1 ? "" : "s"})`);

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
