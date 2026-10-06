/**
 * The columns and the scales.
 *
 * The SVG from the reference HTML, kept while no approved institutional asset
 * exists. It is inline rather than an external file for two reasons: the
 * gradients are referenced by `id`, and inlining removes a request and a flash
 * of empty box on the most important screen of the site.
 *
 * The `id`s are prefixed because this file and any future illustration sharing
 * a document would otherwise collide and repaint each other's gradients.
 */
export function ColumnsIllustration() {
  return (
    <div className="hero-art">
      <svg
        viewBox="0 0 500 480"
        role="img"
        aria-label="Ilustración arquitectónica de columnas y una balanza jurídica"
        className="block w-full"
      >
        <defs>
          <linearGradient id="wb-bg" x2="1" y2="1">
            <stop stopColor="#314b52" />
            <stop offset="1" stopColor="#10262e" />
          </linearGradient>
          <linearGradient id="wb-stone">
            <stop stopColor="#687772" />
            <stop offset=".5" stopColor="#b3b4a5" />
            <stop offset="1" stopColor="#576964" />
          </linearGradient>
        </defs>

        <rect width="500" height="480" fill="url(#wb-bg)" />
        <circle cx="380" cy="95" r="165" fill="#b28b55" opacity=".08" />

        <path d="M40 95L310 10 460 62 188 149Z" fill="#72817b" />
        <path d="M40 95L188 149 188 172 40 118Z" fill="#3e5555" />

        <g fill="url(#wb-stone)">
          <path d="M80 127h46v282H80z" />
          <path d="M178 164h46v245h-46z" />
          <path d="M278 122h46v287h-46z" />
          <path d="M375 91h46v318h-46z" />
        </g>

        <g stroke="#203e40" opacity=".3" strokeWidth="4">
          <path d="M92 139v265M109 139v265M190 173v231M207 173v231M290 132v272M307 132v272M387 101v303M404 101v303" />
        </g>

        <path d="M0 409h500v71H0z" fill="#1a333c" />

        <g stroke="#d4b17a" fill="none" strokeWidth="3">
          <path d="M250 200v140M204 340h92M177 226h146M190 226l-30 64h60zM310 226l-30 64h60z" />
          <circle cx="250" cy="208" r="8" fill="#d4b17a" />
        </g>

        <path d="M0 445h500" stroke="#a98b5e" opacity=".25" />
      </svg>

      <p className="mt-4 text-sm text-petrol-soft">
        La confianza se construye.
        <small className="mt-1 block text-[10px] tracking-[0.34em] text-slate">
          EL DERECHO NOS CONECTA.
        </small>
      </p>
    </div>
  );
}
