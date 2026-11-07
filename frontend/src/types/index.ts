export interface Product {
  id: number;
  url: string;
  platform: string;
  title: string;
  current_price: string | null;
  target_price: string | null;
  currency: string | null;
  target_currency: string | null;
  is_active: boolean;
  source: string;
}

export interface PriceSnapshot {
  id: number;
  price: string;
  currency: string;
  source: string;
  timestamp: string;
}

export interface History {
  history: PriceSnapshot[];
  stats: { lowest_price: string; highest_price: string; average_price: string; currency: string } | null;
  excluded_legacy_count: number;
  source: string;
}

export interface Status {
  notifications_enabled: boolean;
  writes_enabled: boolean;
  demo: boolean;
}
