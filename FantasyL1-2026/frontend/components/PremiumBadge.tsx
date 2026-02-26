import { PremiumBadgeConfig } from "@/lib/types";

type PremiumBadgeProps = {
  config?: Partial<PremiumBadgeConfig>;
  className?: string;
  size?: "sm" | "md";
};

const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

const DEFAULT_BADGE: PremiumBadgeConfig = {
  enabled: true,
  text: "P",
  color: "#7C3AED",
  shape: "circle"
};

const sizeClassMap: Record<NonNullable<PremiumBadgeProps["size"]>, string> = {
  sm: "h-7 w-7 text-xs",
  md: "h-9 w-9 text-sm"
};

export default function PremiumBadge({
  config,
  className = "",
  size = "md"
}: PremiumBadgeProps) {
  const merged: PremiumBadgeConfig = {
    ...DEFAULT_BADGE,
    ...config
  };
  if (!merged.enabled) {
    return null;
  }

  const text = (merged.text || DEFAULT_BADGE.text).trim().slice(0, 2) || DEFAULT_BADGE.text;
  const color = HEX_COLOR_RE.test(merged.color || "") ? (merged.color || "") : DEFAULT_BADGE.color;
  const shapeClass = merged.shape === "rounded" ? "rounded-lg" : "rounded-full";

  return (
    <span
      aria-label="Premium badge"
      className={`inline-flex shrink-0 items-center justify-center font-bold text-white ${shapeClass} ${sizeClassMap[size]} ${className}`}
      style={{ backgroundColor: color }}
      title="Premium"
    >
      {text}
    </span>
  );
}

