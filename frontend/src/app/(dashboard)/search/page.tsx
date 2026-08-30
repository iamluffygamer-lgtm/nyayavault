"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Input, Button, Card, CardHeader, CardTitle, CardBody, Badge } from "@/components/ui";
import Link from "next/link";

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      executeSearch(q);
    }
  }, [searchParams]);

  const executeSearch = async (q: string) => {
    setLoading(true);
    try {
      const res = await api.searchDocuments({ q });
      setResults(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    router.push(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <>
      <form onSubmit={onSubmit} className="flex gap-4">
        <Input 
          value={query} 
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for documents, text, keywords..."
          className="flex-1"
        />
        <Button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </Button>
      </form>

      {results && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            Found {results.total} results
          </p>
          
          {results.items.map((item: any) => (
            <Card key={item.document_id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle>
                      <Link href={`/documents/${item.document_id}`} className="text-ink hover:underline">
                        {item.title}
                      </Link>
                    </CardTitle>
                    <p className="text-[11px] text-muted mt-1">
                      Case: {item.case_number || "Unknown"} • Version: {item.version} • Uploaded by: {item.uploaded_by}
                    </p>
                  </div>
                  <Badge tone="neutral">{item.document_type}</Badge>
                </div>
              </CardHeader>
              <CardBody>
                {item.snippet ? (
                  <p 
                    className="text-xs text-ink bg-subtle p-3 rounded border border-subtle leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: item.snippet }}
                  />
                ) : (
                  <p className="text-xs text-muted italic">No text snippet available.</p>
                )}
                
                <div className="mt-3">
                  <Badge className="text-[10px]" tone={item.extraction_status === "COMPLETED" ? "ok" : "neutral"}>
                    OCR Status: {item.extraction_status}
                  </Badge>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">Search Documents</h1>
      <Suspense fallback={<div>Loading search...</div>}>
        <SearchContent />
      </Suspense>
    </div>
  );
}
