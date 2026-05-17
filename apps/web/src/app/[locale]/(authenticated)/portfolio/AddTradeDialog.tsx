"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Loader2 } from "lucide-react";
import { useAddTrade } from "@/lib/hooks/usePortfolio";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ── Constants ──
const TRADE_TYPES = ["BUY", "SELL", "DIVIDEND"] as const;
const CURRENCIES = ["EUR", "USD", "GBP", "CHF"] as const;

// ── AddTradeDialog ──
export function AddTradeDialog({ onClose }: { onClose: () => void }) {
  const t = useTranslations("portfolio");

  const [tradeType, setTradeType] = useState<string>("BUY");
  const [tickerSymbol, setTickerSymbol] = useState("");
  const [tickerExchange, setTickerExchange] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState<string>("EUR");
  const [fees, setFees] = useState("0");
  const [notes, setNotes] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const addTrade = useAddTrade();

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!tickerSymbol.trim()) errors.ticker_symbol = t("validation_required");
    if (!quantity.trim() || parseFloat(quantity) <= 0)
      errors.quantity = t("validation_positive");
    if (!price.trim() || parseFloat(price) < 0)
      errors.price = t("validation_nonnegative");
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;

    addTrade.mutate(
      {
        trade_type: tradeType,
        ticker_symbol: tickerSymbol.trim().toUpperCase(),
        ticker_exchange: tickerExchange.trim() || undefined,
        quantity: tradeType === "DIVIDEND" ? "1" : quantity,
        price: price,
        currency,
        fees: fees || "0",
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-xl border shadow-lg w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <Card className="border-0 shadow-none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              {t("addTrade")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Trade Type */}
            <div className="space-y-2">
              <Label>{t("tradeType")}</Label>
              <div className="flex gap-2">
                {TRADE_TYPES.map((type) => (
                  <Button
                    key={type}
                    type="button"
                    variant={tradeType === type ? "default" : "outline"}
                    size="sm"
                    onClick={() => setTradeType(type)}
                  >
                    {t(type.toLowerCase())}
                  </Button>
                ))}
              </div>
            </div>

            {/* Ticker */}
            <div className="space-y-2">
              <Label htmlFor="ticker_symbol">{t("ticker")}</Label>
              <Input
                id="ticker_symbol"
                value={tickerSymbol}
                onChange={(e) => setTickerSymbol(e.target.value)}
                placeholder="AAPL"
                className="uppercase"
              />
              {fieldErrors.ticker_symbol && (
                <p className="text-xs text-destructive">{fieldErrors.ticker_symbol}</p>
              )}
            </div>

            {/* Exchange */}
            <div className="space-y-2">
              <Label htmlFor="ticker_exchange">{t("exchange")}</Label>
              <Input
                id="ticker_exchange"
                value={tickerExchange}
                onChange={(e) => setTickerExchange(e.target.value)}
                placeholder="NASDAQ (optional)"
              />
            </div>

            {/* Quantity + Price */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="quantity">
                  {t("quantity")}
                  {tradeType === "DIVIDEND" && (
                    <span className="text-muted-foreground text-xs ml-1">
                      ({t("auto")})
                    </span>
                  )}
                </Label>
                <Input
                  id="quantity"
                  type="number"
                  step="0.0001"
                  min="0"
                  value={tradeType === "DIVIDEND" ? "1" : quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  disabled={tradeType === "DIVIDEND"}
                />
                {fieldErrors.quantity && (
                  <p className="text-xs text-destructive">{fieldErrors.quantity}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="price">
                  {tradeType === "DIVIDEND" ? t("dividend") : t("price")}
                </Label>
                <Input
                  id="price"
                  type="number"
                  step="0.01"
                  min="0"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                />
                {fieldErrors.price && (
                  <p className="text-xs text-destructive">{fieldErrors.price}</p>
                )}
              </div>
            </div>

            {/* Currency + Fees */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="currency">{t("currency")}</Label>
                <select
                  id="currency"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="h-9 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fees">{t("fees")}</Label>
                <Input
                  id="fees"
                  type="number"
                  step="0.01"
                  min="0"
                  value={fees}
                  onChange={(e) => setFees(e.target.value)}
                />
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="notes">{t("notes")}</Label>
              <Input
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("notes_placeholder")}
              />
            </div>

            {/* Error from API */}
            {addTrade.isError && (
              <p className="text-sm text-destructive">
                {(addTrade.error as Error)?.message || t("tradeError")}
              </p>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <Button variant="outline" className="flex-1" onClick={onClose}>
                {t("cancel")}
              </Button>
              <Button
                className="flex-1 gap-2"
                onClick={handleSubmit}
                disabled={addTrade.isPending}
              >
                {addTrade.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : null}
                {t("submit")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
