import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getBarkSettings, updateBarkSettings } from "@/features/settings/api";

export function BarkSettings({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["settings", "notifications"], queryFn: getBarkSettings });
  const mutation = useMutation({
    mutationFn: updateBarkSettings,
    onSuccess: (data) => {
      setUrl("");
      client.setQueryData(["settings", "notifications"], data);
    },
  });
  const busy = disabled || query.isPending || mutation.isPending;
  const error = query.error ?? mutation.error;

  return (
    <section className="space-y-3 rounded-xl border bg-card p-5">
      <h3 className="text-sm font-semibold">{t("settings.bark.title")}</h3>
      <p className="text-xs text-muted-foreground">{t("settings.bark.description")}</p>
      <p role="status" className="text-sm">
        {query.data ? t(query.data.configured ? "settings.bark.enabled" : "settings.bark.disabled") : null}
      </p>
      {error ? <AlertMessage variant="error">{error.message}</AlertMessage> : null}
      <form className="space-y-2" onSubmit={(event) => {
        event.preventDefault();
        if (url.trim()) mutation.mutate(url.trim());
      }}>
        <Label htmlFor="bark-url">{t("settings.bark.url")}</Label>
        <Input id="bark-url" type="password" autoComplete="off" value={url}
          placeholder="https://api.day.app/…" disabled={busy}
          onChange={(event) => setUrl(event.target.value)} />
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={busy || !url.trim()}>{t("common.actions.save")}</Button>
          <Button type="button" size="sm" variant="outline" disabled={busy || !query.data?.configured}
            onClick={() => mutation.mutate(null)}>{t("common.actions.disable")}</Button>
        </div>
      </form>
    </section>
  );
}
