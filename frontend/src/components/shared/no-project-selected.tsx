import * as React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface NoProjectSelectedProps {
  readonly pageTitle: string;
  readonly description: string;
}

export function NoProjectSelected({
  pageTitle,
  description,
}: NoProjectSelectedProps): React.JSX.Element {
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6">{pageTitle}</h1>
      <div className="flex flex-col items-center justify-center py-16 text-center space-y-4">
        <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
        <Button asChild size="sm" variant="default">
          <Link to="/">Go to Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
