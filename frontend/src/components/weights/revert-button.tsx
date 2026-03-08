import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

interface RevertButtonProps {
  readonly onRevert: () => void;
  readonly isReverting: boolean;
  readonly isDisabled: boolean;
}

export function RevertButton({
  onRevert,
  isReverting,
  isDisabled,
}: RevertButtonProps): React.JSX.Element {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" size="sm" disabled={isReverting || isDisabled}>
          {isReverting ? "Reverting…" : "Revert to Pre-edit Checkpoint"}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revert to pre-edit checkpoint?</AlertDialogTitle>
          <AlertDialogDescription>
            This will restore the model parameters to the state captured before your last edit. Any
            changes made after that backup will be lost.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onRevert}>Revert</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
