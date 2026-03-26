import { Formatters } from "../lib/formatters";
import type { OrderHistoryItem } from "../types/api";

interface HistoryScreenProps {
  isLoading: boolean;
  orders: OrderHistoryItem[];
  onBack: () => void;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "n/a";
  }
  return parsed.toLocaleString("en-GB", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatQuantity(value: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return parsed.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  });
}

export function HistoryScreen(props: HistoryScreenProps): JSX.Element {
  return (
    <div className="screen portfolio-screen">
      <header className="topbar compact-topbar">
        <div className="brand-row">
          <div className="brand-mark round">
            <span className="material-symbols-outlined">receipt_long</span>
          </div>
          <div className="brand-copy">
            <strong>Orders</strong>
            <span>Trade history</span>
          </div>
        </div>
        <div className="address-pill">{props.orders.length} trades</div>
      </header>

      <section className="stack">
        {props.isLoading ? (
          <>
            <article className="screen-card history-skeleton-card">
              <div className="portfolio-empty-skeleton history-skeleton-title" />
              <div className="portfolio-empty-skeleton history-skeleton-line" />
              <div className="portfolio-empty-skeleton history-skeleton-line short" />
              <div className="portfolio-empty-skeleton history-skeleton-line tiny" />
            </article>
            <article className="screen-card history-skeleton-card">
              <div className="portfolio-empty-skeleton history-skeleton-title" />
              <div className="portfolio-empty-skeleton history-skeleton-line" />
              <div className="portfolio-empty-skeleton history-skeleton-line short" />
              <div className="portfolio-empty-skeleton history-skeleton-line tiny" />
            </article>
          </>
        ) : props.orders.length === 0 ? (
          <article className="screen-card">
            <p className="screen-copy">No trades yet.</p>
          </article>
        ) : (
          props.orders.map((order) => (
            <article className="screen-card" key={order.order_id}>
              <div className="section-head">
                <h3 className="section-title">
                  {order.side.toUpperCase()} {order.asset_id}
                </h3>
                <span className={`signal-pill ${order.side === "buy" ? "buy" : "sell"}`}>
                  {order.side.toUpperCase()}
                </span>
              </div>
              <p className="screen-copy">
                Amount: <strong>{Formatters.currency(order.notional)}</strong> · Qty:{" "}
                <strong>{formatQuantity(order.quantity)} {order.asset_id}</strong>
              </p>
              <p className="screen-copy">
                Fill price: <strong>{Formatters.currency(order.price)}</strong> per {order.asset_id}
              </p>
              <p className="screen-copy">
                Realized PnL:{" "}
                <strong>
                  {Formatters.currency(order.realized_pnl)} ({Formatters.percent(order.realized_pnl_percent)})
                </strong>
              </p>
              <p className="screen-copy muted">{formatTimestamp(order.created_at)}</p>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
