import { CalendarClock, ClipboardList, Crosshair, Package, Shield } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';

const tools = [
  { title: 'Daily Missions Assist', description: 'Guided next steps with confirmation before each action.', icon: ClipboardList },
  { title: 'Battle Report Analyzer', description: 'Review battle reports and understand the outcome.', icon: Crosshair },
  { title: 'Army Preset Manager', description: 'Organize army setups for your next operation.', icon: Shield },
  { title: 'Supply / Campaign Resupply', description: 'Review supply needs and prepare your next resupply.', icon: Package },
];

export function UpcomingToolsPanel() {
  return (
    <Card>
      <CardHeader title="On the horizon" description="New command tools are in development. Availability will be announced when they are ready." />
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {tools.map(({ title, description, icon: Icon }) => (
          <div key={title} className="rounded-xl border border-border/70 bg-surface-muted/30 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Icon className="h-5 w-5 text-accent" aria-hidden="true" />
              <Badge tone="info"><CalendarClock className="h-3 w-3" aria-hidden="true" />Coming soon</Badge>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-foreground">{title}</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
