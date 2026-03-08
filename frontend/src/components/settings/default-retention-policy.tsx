import * as React from "react";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

interface CheckpointRetentionPolicy {
  readonly keepLastN: number;
  readonly alwaysKeepBestEval: boolean;
  readonly alwaysKeepFinal: boolean;
  readonly deleteIntermediatesAfterCompletion: boolean;
}

interface DefaultRetentionPolicyProps {
  readonly initialPolicy?: CheckpointRetentionPolicy;
  readonly onChange: (policy: CheckpointRetentionPolicy) => void;
}

const DEFAULT_POLICY: CheckpointRetentionPolicy = {
  keepLastN: 3,
  alwaysKeepBestEval: true,
  alwaysKeepFinal: true,
  deleteIntermediatesAfterCompletion: true,
};

export function DefaultRetentionPolicy({
  initialPolicy = DEFAULT_POLICY,
  onChange,
}: DefaultRetentionPolicyProps): React.JSX.Element {
  const [keepLastN, setKeepLastN] = useState(String(initialPolicy.keepLastN));
  const [alwaysKeepBestEval, setAlwaysKeepBestEval] = useState(initialPolicy.alwaysKeepBestEval);
  const [alwaysKeepFinal, setAlwaysKeepFinal] = useState(initialPolicy.alwaysKeepFinal);
  const [deleteIntermediatesAfterCompletion, setDeleteIntermediatesAfterCompletion] = useState(
    initialPolicy.deleteIntermediatesAfterCompletion,
  );

  const emitChange = ({
    nextKeepLastN = keepLastN,
    nextAlwaysKeepBestEval = alwaysKeepBestEval,
    nextAlwaysKeepFinal = alwaysKeepFinal,
    nextDeleteIntermediates = deleteIntermediatesAfterCompletion,
  }: {
    nextKeepLastN?: string;
    nextAlwaysKeepBestEval?: boolean;
    nextAlwaysKeepFinal?: boolean;
    nextDeleteIntermediates?: boolean;
  }): void => {
    onChange({
      keepLastN: Number(nextKeepLastN) || DEFAULT_POLICY.keepLastN,
      alwaysKeepBestEval: nextAlwaysKeepBestEval,
      alwaysKeepFinal: nextAlwaysKeepFinal,
      deleteIntermediatesAfterCompletion: nextDeleteIntermediates,
    });
  };

  const handleKeepLastNChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setKeepLastN(e.target.value);
    emitChange({ nextKeepLastN: e.target.value });
  };

  const handleAlwaysKeepBestEvalChange = (checked: boolean): void => {
    setAlwaysKeepBestEval(checked);
    emitChange({ nextAlwaysKeepBestEval: checked });
  };

  const handleAlwaysKeepFinalChange = (checked: boolean): void => {
    setAlwaysKeepFinal(checked);
    emitChange({ nextAlwaysKeepFinal: checked });
  };

  const handleDeleteIntermediatesChange = (checked: boolean): void => {
    setDeleteIntermediatesAfterCompletion(checked);
    emitChange({ nextDeleteIntermediates: checked });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Default Checkpoint Retention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="keep-last-n">Keep Last N Checkpoints</Label>
          <Input
            id="keep-last-n"
            type="number"
            min="1"
            step="1"
            value={keepLastN}
            onChange={handleKeepLastNChange}
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="always-keep-best-eval">Always keep best eval checkpoint</Label>
          <Switch
            id="always-keep-best-eval"
            checked={alwaysKeepBestEval}
            onCheckedChange={handleAlwaysKeepBestEvalChange}
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="always-keep-final">Always keep final checkpoint</Label>
          <Switch
            id="always-keep-final"
            checked={alwaysKeepFinal}
            onCheckedChange={handleAlwaysKeepFinalChange}
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="delete-intermediates">Delete intermediates after completion</Label>
          <Switch
            id="delete-intermediates"
            checked={deleteIntermediatesAfterCompletion}
            onCheckedChange={handleDeleteIntermediatesChange}
          />
        </div>
      </CardContent>
    </Card>
  );
}
