export interface Notification {
  readonly id: string;
  readonly type: string;
  readonly title: string;
  readonly subtitle: string | null;
  readonly createdAt: string;
  readonly readAt: string | null;
}
