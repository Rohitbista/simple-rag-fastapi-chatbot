import { useState } from 'react';
import { ingestDataApiV1SuperadminIngestPost } from '../../client/sdk.gen';
import { Button, Alert, Card } from '../shared/ui';

export function SuperadminIngestPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleIngest = async () => {
    if (!confirm('Re-index the vector store? This may take a while.')) return;
    setIsLoading(true);
    setResult(null);
    const res = await ingestDataApiV1SuperadminIngestPost();
    setIsLoading(false);
    if (res.data) {
      setResult({ type: 'success', message: res.data.message ?? 'Ingestion completed' });
    } else {
      setResult({ type: 'error', message: 'Ingestion failed. Check the backend logs.' });
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Data Ingest</h1>
        <p className="text-sm text-gray-500 mt-0.5">Rebuild and hot-swap the vector store</p>
      </div>

      <Card className="p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center text-2xl shrink-0">
            📥
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900 mb-1">Re-index vector store</h2>
            <p className="text-sm text-gray-500 mb-4">
              Triggers a full re-ingestion of source data. The refreshed vector store is hot-swapped
              into the backend without a restart. Run this after updating source documents.
            </p>
            {result && (
              <div className="mb-4">
                <Alert variant={result.type === 'success' ? 'success' : 'error'} onDismiss={() => setResult(null)}>
                  {result.message}
                </Alert>
              </div>
            )}
            <Button onClick={handleIngest} isLoading={isLoading} size="lg">
              {isLoading ? 'Indexing…' : 'Run ingestion'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}