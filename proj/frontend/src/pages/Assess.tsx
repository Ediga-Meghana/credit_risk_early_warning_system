import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Loader2, Upload, Calculator, Search, Building2, AlertTriangle, ExternalLink } from "lucide-react";
import { companies, prediction, yahoo } from "../services";
import { download } from "../services/api";
import { Card, Button, toast } from "../components/ui";

function CompanySelect({ value, onChange }: any) {
  const c = useQuery({ queryKey: ["companies", ""], queryFn: () => companies.list("") });
  return <select className="input mt-1" aria-label="Company" value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">Choose a company…</option>
    {(c.data?.items || []).map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}
  </select>;
}
export function NewAssessment() {
  const [query, setQuery] = useState("");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const nav = useNavigate();
  const qc = useQueryClient();
  const search = useQuery({
    queryKey: ["yahoo-search", query],
    queryFn: () => yahoo.search(query.trim()),
    enabled: query.trim().length >= 2,
    retry: false,
  });
  const profile = useQuery({
    queryKey: ["yahoo-company", selectedSymbol],
    queryFn: () => yahoo.company(selectedSymbol),
    enabled: Boolean(selectedSymbol),
    retry: false,
  });
  const assess = useMutation({
    mutationFn: () => yahoo.assess(selectedSymbol),
    onSuccess: (result: any) => {
      ["assessments", "dash-summary", "dash-dist", "dash-recent", "notifications", "company", "companies"].forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
      toast("success", `Yahoo Finance screening completed for ${selectedSymbol}.`);
      nav(`/assessments/${result.id}`);
    },
    onError: (error: any) => toast("error", error.message || "Unable to assess this company."),
  });
  const fmtMoney = (value: any, currency: string) => value == null
    ? "Not reported"
    : `${currency === "Reported currency" ? "" : `${currency} `}${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  return <div className="space-y-5">
    <Card className="overflow-hidden border-primary/20 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-primary-light p-3 text-primary"><Building2 size={22} /></div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">Yahoo Finance · Live lookup</p>
          <h2 className="mt-1 text-xl font-semibold sm:text-2xl">Company risk assessment</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Search for a publicly listed company by name or ticker. We’ll retrieve its available financial statements and prepare supported model inputs automatically. You do not need to enter financial ratios manually.</p>
        </div>
      </div>
      <div className="mt-5 flex flex-col gap-2 sm:flex-row">
        <div className="relative min-w-0 flex-1">
          <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input className="input pl-10" value={query} onChange={(event) => { setQuery(event.target.value); setSelectedSymbol(""); }} placeholder="Search company name or ticker, e.g. Microsoft or TCS.NS" aria-label="Search Yahoo Finance companies" />
        </div>
        <Button variant="secondary" disabled={query.trim().length < 2 || search.isFetching} onClick={() => search.refetch()}>
          {search.isFetching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Search companies
        </Button>
      </div>
      {query.trim().length > 0 && query.trim().length < 2 && <p className="mt-2 text-xs text-muted">Type at least 2 characters to search.</p>}
      {search.isError && <p role="alert" className="mt-3 text-sm text-danger">{(search.error as any)?.message || "Yahoo Finance search failed. Check the backend terminal and internet connection."}</p>}
      {search.isFetching && <p className="mt-3 text-sm text-muted"><Loader2 size={14} className="mr-2 inline animate-spin" />Searching Yahoo Finance…</p>}
      {(search.data?.items || []).length > 0 && !selectedSymbol && <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {search.data.items.map((item: any) => <button key={item.symbol} type="button" onClick={() => setSelectedSymbol(item.symbol)} className="flex items-center gap-3 rounded-xl border border-line p-3 text-left transition hover:border-primary hover:bg-primary-light/30">
          <div className="rounded-lg bg-soft p-2 text-primary"><Building2 size={18} /></div>
          <div className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{item.name}</span><span className="mt-0.5 block text-xs text-muted">{item.symbol}{item.exchange ? ` · ${item.exchange}` : ""}{item.type ? ` · ${item.type}` : ""}</span></div><ExternalLink size={15} className="shrink-0 text-muted" />
        </button>)}
      </div>}
      {search.data && search.data.items?.length === 0 && query.trim().length >= 2 && !search.isFetching && <p className="mt-3 text-sm text-muted">No companies found. Try a ticker such as MSFT, AAPL or TCS.NS.</p>}
      {selectedSymbol && <div className="mt-5 rounded-xl border border-line bg-soft/40 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div><p className="text-xs font-semibold uppercase tracking-wider text-primary">Selected ticker · {selectedSymbol}</p><h3 className="mt-1 text-lg font-semibold">{profile.data?.name || (profile.isLoading ? "Loading company details…" : selectedSymbol)}</h3><p className="mt-1 text-sm text-muted">{profile.data?.sector || "Public company"}{profile.data?.country ? ` · ${profile.data.country}` : ""}</p></div>
          <button type="button" className="self-start text-sm font-medium text-primary hover:underline" onClick={() => setSelectedSymbol("")}>Choose another</button>
        </div>
        {profile.isLoading && <p className="mt-3 text-sm text-muted"><Loader2 size={14} className="mr-2 inline animate-spin" />Fetching available financial statements…</p>}
        {profile.isError && <p role="alert" className="mt-3 text-sm text-danger">{(profile.error as any)?.message || "Unable to load financial statements. Check the backend terminal."}</p>}
        {profile.data && <>
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">{[["Revenue", profile.data.financials.revenue], ["Operating income", profile.data.financials.operating_income], ["Total assets", profile.data.financials.total_assets], ["Total liabilities", profile.data.financials.total_liabilities]].map(([label, value]: any) => <div key={label} className="rounded-lg border border-line bg-white p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 break-words text-sm font-semibold">{fmtMoney(value, profile.data.financials.currency)}</p></div>)}</div>
          <div className="mt-4 flex flex-col gap-3 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-amber-950 sm:flex-row sm:items-start">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" /><div className="min-w-0 flex-1"><p className="text-sm font-semibold">Exploratory screening · {profile.data.feature_coverage}/{profile.data.feature_total} model features derived</p><p className="mt-1 text-xs leading-5">The model was trained on Polish bankruptcy data, not a representative sample of Yahoo-listed companies. Unavailable features may be imputed, so this result is not a calibrated credit decision.</p>{profile.data.missing_features?.length > 0 && <p className="mt-1 text-xs">Not derived from statements: {profile.data.missing_features.join(", ")}</p>}</div>
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center"><Button disabled={assess.isPending || profile.data.feature_coverage < 5} onClick={() => assess.mutate()}>{assess.isPending ? <Loader2 size={16} className="animate-spin" /> : <Calculator size={16} />} Predict risk for {selectedSymbol}</Button><span className="text-xs text-muted">Source: Yahoo Finance · latest available annual statements</span></div>
          {profile.data.feature_coverage < 5 && <p className="mt-2 text-sm text-danger">There is not enough financial data to run even an exploratory screening for this company.</p>}
        </>}
      </div>}
    </Card>
    <Card className="p-4 sm:p-5"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 text-amber-600" size={19}/><div><h3 className="font-semibold">Please note</h3><p className="mt-1 text-sm leading-6 text-muted">Yahoo Finance covers many publicly listed companies, but it does not provide complete statements for every ticker. This research prototype may not be suitable for private companies or real lending decisions. If data is missing, the app will show the limitation rather than ask you to invent financial figures.</p></div></div></Card>
  </div>;
}

export function Batch() {
  const [cid, setCid] = useState(""); const [file, setFile] = useState<File | null>(null); const qc = useQueryClient(); const feats = useQuery({ queryKey: ["features"], queryFn: prediction.features });
  const m = useMutation({ mutationFn: () => prediction.batch(Number(cid), file!), onSuccess: () => { ["assessments", "dash-summary", "dash-dist", "dash-recent", "notifications"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast("success", "Batch prediction completed."); }, onError: (e: any) => toast("error", e.message) });
  return <div className="space-y-4"><Card className="space-y-4 p-5"><div className="flex items-center gap-2"><Upload className="text-primary" size={20}/><h3 className="font-semibold">Assess multiple records from a CSV file</h3></div><p className="text-sm leading-6 text-muted">For bulk analysis, upload a CSV containing the model feature columns. This option is designed for analysts or users who already have prepared dataset ratios; ordinary users should use the Yahoo Finance company search for a single listed company.</p>
    <div className="rounded-xl bg-soft p-3 text-sm"><b>CSV format</b><p className="mt-1 text-muted">Expected columns include feature keys such as <code>Attr26</code>. Missing columns are filled using training-set medians. Maximum 500 rows.</p><p className="mt-2 text-xs text-muted">Required model columns: {(feats.data || []).map((f: any) => f.key).join(", ")}</p></div>
    <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Company<CompanySelect value={cid} onChange={setCid} /></label><label className="text-sm font-medium">CSV file<input className="input mt-1" type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label></div>
    <Button disabled={!cid || !file || m.isPending} onClick={() => m.mutate()}>{m.isPending ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}Run batch assessment</Button></Card>
    {m.data && <Card className="flex items-center justify-between p-5"><div><b>{m.data.count}</b> rows processed. Batch <code>{m.data.batch_id}</code></div><Button variant="ghost" onClick={() => download(`/api/assessments/batch/${m.data.batch_id}/download`, `batch_${m.data.batch_id}.csv`)}>Download results</Button></Card>}</div>;
}
