
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  RefreshCw,
  Plus,
  AlertTriangle,
  Clock3,
  BarChart3,
} from "lucide-react";
import { monitoring } from "../services";
import {
  Button,
  Card,
  ErrorState,
  Skeleton,
  toast,
  RiskBadge,
  EmptyState,
} from "../components/ui";

export default function Monitoring() {
  const [symbol, setSymbol] = useState("");
  const qc = useQueryClient();

  const list = useQuery({
    queryKey: ["monitoring"],
    queryFn: monitoring.list,
  });

  const add = useMutation({
    mutationFn: () => monitoring.add(symbol.trim().toUpperCase()),
    onSuccess: (r: any) => {
      toast("success", r.message || "Monitoring started.");
      setSymbol("");
      qc.invalidateQueries({ queryKey: ["monitoring"] });
    },
    onError: (e: any) =>
      toast("error", e.message || "Could not add company."),
  });

  const check = useMutation({
    mutationFn: monitoring.check,
    onSuccess: (r: any) => {
      toast("success", `Checked ${r.checked} monitored companies.`);
      qc.invalidateQueries({ queryKey: ["monitoring"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (e: any) =>
      toast("error", e.message || "Monitoring check failed."),
  });

  const items = list.data?.items || [];

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-primary-light p-3 text-primary">
            <Activity size={22} />
          </div>

          <div>
            <h2 className="text-lg font-semibold">
              Financial Risk Monitoring
            </h2>
            <p className="mt-1 text-sm text-muted">
              Automatically check daily stock-market data and refreshed
              company statements. Save dated snapshots, compare changes,
              reassess fundamental credit risk when statements change,
              and flag market stress.
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <input
            className="input max-w-xs"
            placeholder="Ticker, e.g. AAPL"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            maxLength={30}
          />

          <Button
            disabled={!symbol.trim() || add.isPending}
            onClick={() => add.mutate()}
          >
            <Plus size={16} />
            {add.isPending ? "Adding…" : "Start monitoring"}
          </Button>

          <Button
            variant="secondary"
            disabled={check.isPending || !items.length}
            onClick={() => check.mutate()}
          >
            <RefreshCw
              size={16}
              className={check.isPending ? "animate-spin" : ""}
            />
            {check.isPending ? "Checking…" : "Check for updates"}
          </Button>
        </div>

        <p className="mt-3 text-xs text-muted">
          Automatic checks run every 24 hours while the backend process is
          awake. Stock quotes usually update on trading days; company
          statements update when published. The XGBoost credit probability
          uses financial ratios, while price movements create a separate
          market-stress signal—not a calibrated default probability. For
          reliable monitoring, keep the backend awake or use an external
          scheduler.
        </p>
      </Card>

      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : list.isError ? (
        <Card>
          <ErrorState
            message={(list.error as any).message}
            onRetry={list.refetch}
          />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title="No companies monitored yet"
            text="Enter a Yahoo Finance ticker above to save the first financial snapshot."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item: any) => (
            <Card key={item.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">
                    {item.company_name || item.symbol}{" "}
                    <span className="text-xs text-muted">
                      ({item.symbol})
                    </span>
                  </h3>

                  <p className="mt-1 text-xs text-muted">
                    <Clock3 size={13} className="mr-1 inline" />
                    Last snapshot:{" "}
                    {item.latest?.observed_at
                      ? new Date(item.latest.observed_at).toLocaleString()
                      : "Not yet checked"}
                    {" · "}Source period:{" "}
                    {item.latest?.source_period || "Unknown"}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {item.latest?.risk_level && (
                    <RiskBadge level={item.latest.risk_level} />
                  )}

                  <span
                    className={`rounded-full px-2 py-1 text-xs font-medium ${
                      item.latest?.market_signal_level === "critical"
                        ? "bg-red-100 text-red-800"
                        : item.latest?.market_signal_level === "high"
                          ? "bg-orange-100 text-orange-800"
                          : item.latest?.market_signal_level === "moderate"
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-soft text-muted"
                    }`}
                  >
                    Market signal:{" "}
                    {item.latest?.market_signal_level || "unknown"}
                  </span>
                </div>
              </div>

              {item.latest && (
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">
                      Fundamental credit-risk probability
                    </p>
                    <p className="text-xl font-semibold">
                      {item.latest.risk_probability == null
                        ? "—"
                        : `${(item.latest.risk_probability * 100).toFixed(1)}%`}
                    </p>
                  </div>

                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">Latest stock close</p>
                    <p className="text-xl font-semibold">
                      {item.latest.market_data?.close == null
                        ? "—"
                        : item.latest.market_data.close.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted">
                      As of {item.latest.market_data?.as_of || "unavailable"}
                    </p>
                  </div>

                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">Daily stock change</p>
                    <p
                      className={`text-xl font-semibold ${
                        (item.latest.market_data?.daily_change_pct ?? 0) < 0
                          ? "text-red-700"
                          : ""
                      }`}
                    >
                      {item.latest.market_data?.daily_change_pct == null
                        ? "—"
                        : `${item.latest.market_data.daily_change_pct}%`}
                    </p>
                    <p className="text-xs text-muted">
                      Compared with previous close
                    </p>
                  </div>

                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">
                      Five-trading-day change
                    </p>
                    <p
                      className={`text-xl font-semibold ${
                        (item.latest.market_data?.five_day_change_pct ?? 0) < 0
                          ? "text-red-700"
                          : ""
                      }`}
                    >
                      {item.latest.market_data?.five_day_change_pct == null
                        ? "—"
                        : `${item.latest.market_data.five_day_change_pct}%`}
                    </p>
                    <p className="text-xs text-muted">
                      Separate from credit probability
                    </p>
                  </div>

                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">Latest trading volume</p>
                    <p className="text-xl font-semibold">
                      {item.latest.market_data?.volume == null
                        ? "—"
                        : item.latest.market_data.volume.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted">
                      Shares traded on latest source date
                    </p>
                  </div>

                  <div className="rounded-lg bg-soft p-3">
                    <p className="text-xs text-muted">
                      20-day annualized volatility
                    </p>
                    <p className="text-xl font-semibold">
                      {item.latest.market_data?.twenty_day_volatility_pct == null
                        ? "—"
                        : `${item.latest.market_data.twenty_day_volatility_pct}%`}
                    </p>
                    <p className="text-xs text-muted">
                      Historical market movement
                    </p>
                  </div>
                </div>
              )}

              {item.latest && (
                <div className="mt-3 rounded-lg border border-line p-3">
                  <p className="text-sm font-semibold">
                    <BarChart3 size={15} className="mr-1 inline" />
                    Loan decision support
                  </p>
                  <p className="mt-1 text-sm">
                    {item.latest.risk_level === "low"
                      ? "Potentially suitable for further review"
                      : item.latest.risk_level === "moderate"
                        ? "Review required"
                        : "High caution — manual review"}
                    ; use financial statements, market alerts and lender
                    policy checks. This is not an automatic approval or
                    denial.
                  </p>
                </div>
              )}

              {(item.latest?.change_summary || []).length > 0 && (
                <div className="mt-3">
                  <h4 className="mb-2 text-sm font-semibold">
                    <AlertTriangle size={15} className="mr-1 inline" />
                    Latest market and financial changes
                  </h4>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-muted">
                          <th className="p-2">Indicator</th>
                          <th>Previous</th>
                          <th>Current</th>
                          <th>Change</th>
                        </tr>
                      </thead>

                      <tbody>
                        {item.latest.change_summary.map((c: any) => (
                          <tr
                            key={c.field}
                            className="border-t border-line"
                          >
                            <td className="p-2">
                              {c.field
                                .replaceAll("_", " ")
                                .replaceAll(".", " · ")}
                            </td>
                            <td>
                              {typeof c.previous === "number"
                                ? c.previous.toLocaleString()
                                : String(c.previous ?? "—")}
                            </td>
                            <td>
                              {typeof c.current === "number"
                                ? c.current.toLocaleString()
                                : String(c.current ?? "—")}
                            </td>
                            <td>
                              {c.percent_change == null
                                ? "—"
                                : `${c.percent_change}%`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
