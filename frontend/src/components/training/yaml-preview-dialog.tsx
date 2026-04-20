import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/shared/code-block";

interface YamlPreviewDialogProps {
  readonly isOpen: boolean;
  readonly yamlContent: string;
  readonly onClose: () => void;
}

export function YamlPreviewDialog({
  isOpen,
  yamlContent,
  onClose,
}: YamlPreviewDialogProps): React.JSX.Element {
  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-w-[720px]">
        <DialogHeader>
          <DialogTitle>Training config · YAML preview</DialogTitle>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          <CodeBlock code={yamlContent} language="yaml" />
        </div>
        <DialogFooter>
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
