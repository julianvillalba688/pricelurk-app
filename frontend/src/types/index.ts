export interface User {
  id: number;
  email: string;
}

export interface Product {
  id: number;
  url: string;
  platform: string;
  title: string;
  current_price: number;
  target_price: number;
  image_url: string;
  is_active: boolean;
}

export interface PriceSnapshot {
  id: number;
  price: number;
  timestamp: string;
}
