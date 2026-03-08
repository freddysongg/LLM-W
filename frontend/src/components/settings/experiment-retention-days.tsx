import * as React from "react";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

interface ExperimentRetentionDaysProps {
  readonly initialDays?: number;
  readonly onChange: (days: number) => void;
}

const DEFAULT_RETENTION_DAYS = 90;

export function ExperimentRetentionDays({
  initialDays = DEFAULT_RETENTION_DAYS,
  onChange,
}: ExperimentRetentionDaysProps): React.JSX.Element {
  const [retentionDays, setRetentionDays] = useState(String(initialDays));

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setRetentionDays(e.target.value);
    const parsed = Number(e.target.value);
    if (parsed > 0) {
      onChange(parsed);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Experiment Retention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <Label htmlFor="experiment-retention-days">Retain experiment data for (days)</Label>
        <Input
          id="experiment-retention-days"
          type="number"
          min="1"
          step="1"
          value={retentionDays}
          onChange={handleChange}
        />
      </CardContent>
    </Card>
  );
}
