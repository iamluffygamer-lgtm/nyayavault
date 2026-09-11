"use client";
import { AppShell } from '@/components/layout/app-shell';

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Input, Button, Card, CardHeader, CardTitle, CardBody, Badge, Skeleton, EmptyState } from "@/components/ui";
import { PageHeader } from "@/components/layout/app-shell";
import { Search as SearchIcon, FileText, FolderKanban, ChevronRight } from "lucide-react";
import Link from "next/link";
import { titleCase } from "@/lib/utils";

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      executeSearch(q);
    }
  }, [searchParams]);

  const executeSearch = async (q: string) => {
    setLoading(true);
    setHasSearched(true);
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
    <div className="max-w-5xl space-y-8">
      <form onSubmit={onSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted" />
          <Input 
            value={query} 
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases, documents, and extracted text..."
            className="pl-11 h-14 text-base rounded-sm border-line bg-surface shadow-sm"
          />
        </div>
        <Button type="submit" size="lg" disabled={loading} className="h-14 px-8 text-base shadow-sm">
          {loading ? "Searching..." : "Search"}
        </Button>
      </form>

      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {!loading && hasSearched && results && results.items.length === 0 && (
        <EmptyState 
          icon={<SearchIcon className="h-8 w-8" />}
          title="No results found" 
          description={`No documents or cases matched your query "${query}".`} 
        />
      )}

      {!loading && results && results.items.length > 0 && (
        <div className="space-y-5">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h3 className="text-sm font-semibold text-ink">
              Showing {results.items.length} {results.items.length === 1 ? 'result' : 'results'} for &quot;{query}&quot;
            </h3>
            <span className="text-[11px] text-muted uppercase tracking-wider">
              Global Search
            </span>
          </div>
          
          <div className="space-y-4">
            {results.items.map((item: any) => (
              <Card key={item.document_id} className="hover:shadow-md transition-shadow border-l-4 border-l-brand">
                <CardBody className="p-0">
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_250px] md:divide-x divide-line">
                    
                    <div className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <Link href={`/documents/${item.document_id}`} className="flex items-center gap-2 group">
                            <FileText className="h-4 w-4 text-brand" />
                            <h4 className="text-base font-bold text-ink group-hover:underline group-hover:text-brand transition-colors">
                              {item.title}
                            </h4>
                          </Link>
                          
                          <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                            <span className="flex items-center gap-1">
                              <FolderKanban className="h-3.5 w-3.5" /> 
                              Case <span className="font-mono text-ink font-medium">{item.case_number || "Unknown"}</span>
                            </span>
                            <span className="w-1 h-1 rounded-full bg-line" />
                            <span>Version {item.version}</span>
                          </div>
                        </div>
                        <Badge tone="neutral">{titleCase(item.document_type || "document")}</Badge>
                      </div>

                      {item.snippet && (
                        <div className="mt-4">
                          <p className="text-[10px] uppercase tracking-widest text-faint mb-1.5 font-semibold">Matched Content</p>
                          <p 
                            className="text-xs text-ink bg-elevated/50 p-3.5 rounded-sm border border-line leading-relaxed [&>b]:text-brand [&>b]:bg-brand/10 [&>b]:px-0.5"
                            dangerouslySetInnerHTML={{ __html: item.snippet }}
                          />
                        </div>
                      )}
                    </div>

                    <div className="p-5 bg-elevated/20 flex flex-col justify-between">
                      <div className="space-y-3">
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-faint font-semibold">Uploaded By</p>
                          <p className="text-xs font-medium text-ink mt-0.5">{item.uploaded_by}</p>
                        </div>
                        
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-faint font-semibold">Text Processing</p>
                          <p className="mt-1">
                            {item.extraction_status === "COMPLETED" ? (
                              <Badge tone="ok" className="text-[10px]">Searchable</Badge>
                            ) : (
                              <Badge tone="neutral" className="text-[10px]">{titleCase(item.extraction_status || "Pending")}</Badge>
                            )}
                          </p>
                        </div>
                      </div>
                      
                      <Link href={`/documents/${item.document_id}`}>
                        <Button variant="secondary" size="sm" className="w-full mt-4">
                          View Record
                          <ChevronRight className="h-3.5 w-3.5 ml-1" />
                        </Button>
                      </Link>
                    </div>

                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <AppShell>
      <PageHeader 
        title="Global Search"
        description="Search across all cases, records, and extracted document text."
      />
      <Suspense fallback={<div className="flex justify-center p-10"><Skeleton className="h-10 w-full max-w-xl" /></div>}>
        <SearchContent />
      </Suspense>
    </AppShell>
  );
}
