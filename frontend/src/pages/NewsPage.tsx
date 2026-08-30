import React, { useEffect, useState } from 'react';
import { ExternalLink, Filter, Newspaper, Tag } from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { NewsItem, NewsData } from '../types/news';
import { SectionHeader } from '../components/common/SectionHeader';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';

export const NewsPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [newsRes, setNewsRes] = useState<ApiResponse<NewsData> | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  useEffect(() => {
    let isMounted = true;
    const fetchNews = async () => {
      setLoading(true);
      try {
        const res = await client.getNews();
        if (isMounted) setNewsRes(res);
      } catch (err) {
        console.error('Failed to load news:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchNews();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  return (
    <div id="news-page" className="space-y-6">
      <SectionHeader
        title="Market News & Catalyst Intelligence"
        subtitle="Institutional news feeds, corporate disclosures, and earnings catalyst context"
        freshness={newsRes?.freshness}
        timestamp={newsRes?.timestamp}
      />

      <ApiStateWrapper<NewsData>
        response={newsRes}
        isLoading={loading}
        skeletonType="card"
        skeletonRows={4}
      >
        {(newsData: NewsData) => {
          const items = newsData.items || [];
          const categories = Array.from(new Set(items.map((i) => i.eventCategory)));
          const filtered = selectedCategory === 'ALL'
            ? items
            : items.filter((i) => i.eventCategory === selectedCategory);

          return (
            <div className="space-y-4">
              {/* Category Filter */}
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                <button
                  onClick={() => setSelectedCategory('ALL')}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
                    selectedCategory === 'ALL'
                      ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900'
                      : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                  }`}
                >
                  All Feeds ({items.length})
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
                      selectedCategory === cat
                        ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900'
                        : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                    }`}
                  >
                    {cat.replace('_', ' ')}
                  </button>
                ))}
              </div>

              {/* News Items List */}
              <div className="space-y-3">
                {filtered.map((item) => (
                  <div
                    key={item.id}
                    id={`news-item-${item.id}`}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs hover:border-slate-300 dark:hover:border-slate-700 transition-colors space-y-2.5"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono">
                          {item.eventCategory.replace('_', ' ')}
                        </span>
                        <span className="text-xs font-bold text-slate-500">
                          {item.publisher}
                        </span>
                        <span className="text-xs text-slate-400">•</span>
                        <span className="text-xs font-mono text-slate-400">
                          {item.timeAgo ?? item.timestamp ?? '—'}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 flex-wrap">
                        {item.symbols.map((sym) => (
                          <span
                            key={sym}
                            className="text-[11px] font-bold font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20"
                          >
                            {sym}
                          </span>
                        ))}
                      </div>
                    </div>

                    <h3 className="text-sm sm:text-base font-bold text-slate-900 dark:text-slate-100 leading-snug">
                      {item.title}
                    </h3>

                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      {item.catalystContext}
                    </p>

                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
                      <div className="flex items-center gap-2">
                        <span>Quality: <strong className="font-mono text-slate-700 dark:text-slate-300">{item.sourceQuality.replace(/_/g, ' ')}</strong></span>
                      </div>
                      <span className={`font-semibold px-2 py-0.5 rounded text-[10px] uppercase ${
                        item.sentimentImpact === 'POSITIVE'
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                          : item.sentimentImpact === 'NEGATIVE'
                          ? 'bg-rose-500/15 text-rose-700 dark:text-rose-400'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                      }`}>
                        {item.sentimentImpact}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
