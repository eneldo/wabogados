import Image from "next/image";

/** One approved asset and aspect ratio for every audience and screen. */
export function BrandLogo({
  size = "header",
  priority = false,
  imageClassName = "",
}: {
  size?: "header" | "sidebar" | "compact" | "login" | "footer";
  priority?: boolean;
  imageClassName?: string;
}) {
  const widths = { header: 164, sidebar: 140, compact: 104, login: 196, footer: 180 };
  return (
    <span className="brand-logo" data-size={size}>
      <Image
        src="/marca/wabogados-logo.webp"
        alt="WABOGADOS"
        width={442}
        height={248}
        sizes={`${widths[size]}px`}
        priority={priority}
        className={`brand-logo__image ${imageClassName}`}
      />
    </span>
  );
}
