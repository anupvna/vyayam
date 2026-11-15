// Original line illustrations for every piece of equipment, drawn for Vyayam on a
// 64x64 grid with one stroke weight and one soft fill, so the whole set reads as a family.
// They use `currentColor`, so the theme decides their colour.
import type { ReactNode } from "react";

const F = { fill: "currentColor", fillOpacity: 0.16 } as const; // soft fill for main masses
const Ground = () => <path d="M6 58H58" opacity={0.35} />;

// Seat + backrest, shared by the seated machines.
const Seat = ({ x }: { x: number }) => (
  <>
    <rect x={x} y={38} width={20} height={5} rx={2.5} {...F} />
    <path d={`M${x + 2} 38L${x} 12L${x + 6} 12L${x + 8} 38Z`} {...F} />
    <path d={`M${x + 10} 43V58`} />
  </>
);

const ART: Record<string, ReactNode> = {
  barbell: (
    <>
      <path d="M3 32H61" />
      <rect x="8" y="19" width="5" height="26" rx="1.5" {...F} />
      <rect x="14" y="24" width="4" height="16" rx="1.5" {...F} />
      <rect x="51" y="19" width="5" height="26" rx="1.5" {...F} />
      <rect x="46" y="24" width="4" height="16" rx="1.5" {...F} />
    </>
  ),
  dumbbells: (
    <>
      <path d="M22 32H42" />
      <rect x="12" y="21" width="10" height="22" rx="3" {...F} />
      <rect x="42" y="21" width="10" height="22" rx="3" {...F} />
      <path d="M8 27V37M56 27V37" />
    </>
  ),
  ez_bar: (
    <>
      <path d="M3 32H15L19 28L24 36L29 28H35L40 36L45 28L49 32H61" />
      <rect x="7" y="22" width="5" height="20" rx="1.5" {...F} />
      <rect x="52" y="22" width="5" height="20" rx="1.5" {...F} />
    </>
  ),
  kettlebells: (
    <>
      <path d="M23 28C20 24 20 15 27 13H37C44 15 44 24 41 28" />
      <circle cx="32" cy="40" r="15" {...F} />
      <path d="M26 36C28 34 36 34 38 36" opacity={0.5} />
    </>
  ),
  trap_bar: (
    <>
      <path d="M20 21H44L53 32L44 43H20L11 32Z" />
      <path d="M25 27V37M39 27V37" />
      <path d="M3 32H11M53 32H61" />
      <rect x="4" y="25" width="4" height="14" rx="1.5" {...F} />
      <rect x="56" y="25" width="4" height="14" rx="1.5" {...F} />
    </>
  ),
  squat_rack: (
    <>
      <path d="M15 6V58M49 6V58M15 8H49M8 58H22M42 58H56" />
      <path d="M15 31H19M49 31H45" />
      <path d="M3 27H61" />
      <rect x="5" y="19" width="4" height="16" rx="1.5" {...F} />
      <rect x="55" y="19" width="4" height="16" rx="1.5" {...F} />
    </>
  ),
  flat_bench: (
    <>
      <rect x="7" y="26" width="50" height="7" rx="3.5" {...F} />
      <path d="M16 33V50M48 33V50M10 50H22M42 50H54" />
    </>
  ),
  adjustable_bench: (
    <>
      <rect x="25" y="34" width="30" height="6" rx="3" {...F} />
      <path d="M23 38L9 15L14 12L28 35Z" {...F} />
      <path d="M32 40V52M48 40V52M22 52H56M20 28L30 46" />
    </>
  ),
  pull_up_bar: (
    <>
      <path d="M16 58V14M48 58V14M5 14H59M5 14L2 8M59 14L62 8M10 58H22M42 58H54" />
      <rect x="20" y="11" width="8" height="6" rx="3" {...F} />
      <rect x="36" y="11" width="8" height="6" rx="3" {...F} />
    </>
  ),
  dip_station: (
    <>
      <rect x="8" y="21" width="17" height="6" rx="3" {...F} />
      <rect x="39" y="21" width="17" height="6" rx="3" {...F} />
      <path d="M24 24V56M40 24V56M14 56H50M24 40H40" />
    </>
  ),
  smith_machine: (
    <>
      <path d="M12 6V58M52 6V58M12 6H52M6 58H58" />
      <path d="M18 6V58M46 6V58" opacity={0.45} />
      <path d="M3 30H61" />
      <rect x="15" y="26" width="6" height="8" rx="1.5" {...F} />
      <rect x="43" y="26" width="6" height="8" rx="1.5" {...F} />
    </>
  ),
  cable_station: (
    <>
      <path d="M8 58V8H56V58M4 58H60" />
      <circle cx="16" cy="13" r="3" />
      <circle cx="48" cy="13" r="3" />
      <path d="M16 16V40M48 16V40" />
      <path d="M13 40H19L18 46H14Z" {...F} />
      <path d="M45 40H51L50 46H46Z" {...F} />
      <rect x="27" y="26" width="10" height="28" rx="1.5" {...F} />
      <path d="M27 33H37M27 40H37M27 47H37" opacity={0.5} />
    </>
  ),
  lat_pulldown: (
    <>
      <path d="M46 58V8H30" />
      <circle cx="30" cy="11" r="3" />
      <path d="M30 14V22M14 25C14 23 15 22 17 22H43C45 22 46 23 46 25" />
      <rect x="20" y="33" width="18" height="4" rx="2" {...F} />
      <rect x="19" y="44" width="20" height="5" rx="2.5" {...F} />
      <path d="M29 49V58M18 58H58" />
      <rect x="50" y="24" width="7" height="30" rx="1.5" {...F} />
    </>
  ),
  cable_row: (
    <>
      <path d="M54 58V18" />
      <circle cx="54" cy="44" r="3" />
      <path d="M51 44H31M31 44L25 40M31 44L25 48" />
      <rect x="5" y="46" width="18" height="5" rx="2.5" {...F} />
      <rect x="37" y="44" width="4" height="14" rx="1" {...F} />
      <path d="M9 51V58M19 51V58M3 58H60" />
    </>
  ),
  leg_press: (
    <>
      <Ground />
      <path d="M16 54L50 12M50 12V58" />
      <path d="M36 22L49 32L43 39L30 29Z" {...F} />
      <path d="M6 36L12 32L25 51L19 55Z" {...F} />
      <path d="M19 55H34" />
    </>
  ),
  hack_squat: (
    <>
      <Ground />
      <path d="M22 56L36 8M30 56L44 8" opacity={0.5} />
      <path d="M31 16L38 18L30 48L23 46Z" {...F} />
      <path d="M26 20L40 24" />
      <path d="M10 50L36 58" />
    </>
  ),
  leg_extension: (
    <>
      <Ground />
      <Seat x={12} />
      <circle cx="36" cy="40" r="3" />
      <path d="M37 43L43 52" />
      <rect x="39" y="50" width="12" height="6" rx="3" {...F} />
    </>
  ),
  leg_curl: (
    <>
      <rect x="5" y="28" width="40" height="7" rx="3.5" {...F} />
      <path d="M13 35V56M37 35V56M4 56H50" />
      <circle cx="47" cy="31" r="3" />
      <path d="M48 28L55 18" />
      <rect x="51" y="11" width="10" height="7" rx="3.5" {...F} />
    </>
  ),
  calf_raise_machine: (
    <>
      <Ground />
      <path d="M44 58V10M44 16H26" />
      <rect x="16" y="15" width="18" height="6" rx="3" {...F} />
      <rect x="14" y="50" width="22" height="8" rx="1.5" {...F} />
      <rect x="48" y="22" width="8" height="32" rx="1.5" {...F} />
    </>
  ),
  hip_thrust_machine: (
    <>
      <Ground />
      <rect x="5" y="30" width="20" height="6" rx="3" {...F} />
      <path d="M11 36V58M21 36V58M28 52H56" />
      <rect x="29" y="34" width="22" height="6" rx="3" {...F} />
      <circle cx="54" cy="30" r="3" />
      <path d="M51 34L53 32" />
    </>
  ),
  chest_press_machine: (
    <>
      <Ground />
      <Seat x={8} />
      <path d="M18 24H44M30 20V28" />
      <rect x="47" y="12" width="9" height="42" rx="1.5" {...F} />
      <path d="M44 24V12H47" />
    </>
  ),
  pec_deck: (
    <>
      <Ground />
      <rect x="22" y="40" width="20" height="5" rx="2.5" {...F} />
      <rect x="26" y="10" width="12" height="30" rx="3" {...F} />
      <path d="M32 45V58" />
      <path d="M26 18C16 19 11 25 10 32M38 18C48 19 53 25 54 32" />
      <rect x="6" y="30" width="8" height="14" rx="3" {...F} />
      <rect x="50" y="30" width="8" height="14" rx="3" {...F} />
    </>
  ),
  shoulder_press_machine: (
    <>
      <Ground />
      <Seat x={8} />
      <path d="M14 8H44M24 8V16M36 8V16M44 8V58" />
      <rect x="47" y="20" width="9" height="34" rx="1.5" {...F} />
    </>
  ),
  row_machine: (
    <>
      <Ground />
      <path d="M21 46L35 18L41 21L27 49Z" {...F} />
      <rect x="6" y="44" width="16" height="5" rx="2.5" {...F} />
      <path d="M14 49V58M40 31H54M54 31V58M46 27V35" />
    </>
  ),
  assisted_pull_up: (
    <>
      <path d="M12 58V8M52 58V8M6 8H58M6 58H58" />
      <path d="M16 15H26M38 15H48" />
      <rect x="22" y="38" width="20" height="5" rx="2.5" {...F} />
      <path d="M32 43V52M24 52H40" />
      <rect x="27" y="20" width="10" height="12" rx="1.5" {...F} />
    </>
  ),
  resistance_bands: (
    <>
      <ellipse cx="32" cy="32" rx="25" ry="14" {...F} />
      <ellipse cx="32" cy="32" rx="17" ry="7" />
    </>
  ),
  suspension_trainer: (
    <>
      <path d="M32 4V13" />
      <circle cx="32" cy="16" r="3" />
      <path d="M30 19L15 46M34 19L49 46M20 34H25M44 34H39" />
      <rect x="9" y="46" width="13" height="6" rx="3" {...F} />
      <rect x="42" y="46" width="13" height="6" rx="3" {...F} />
    </>
  ),
  ab_wheel: (
    <>
      <circle cx="32" cy="32" r="16" {...F} />
      <circle cx="32" cy="32" r="5" />
      <path d="M16 32H48" opacity={0.5} />
      <path d="M5 32H14M50 32H59" strokeWidth={5} />
    </>
  ),
  medicine_ball: (
    <>
      <circle cx="32" cy="32" r="21" {...F} />
      <path d="M11 32C21 25 43 25 53 32M32 11C25 21 25 43 32 53" />
    </>
  ),
  plyo_box: (
    <>
      <path d="M11 22L32 12L53 22V44L32 54L11 44Z" {...F} />
      <path d="M11 22L32 32L53 22M32 32V54" />
    </>
  ),
  treadmill: (
    <>
      <rect x="5" y="44" width="42" height="7" rx="3.5" {...F} />
      <path d="M9 51V56M43 51V56M44 44L52 14M38 28H50" />
      <rect x="46" y="8" width="13" height="7" rx="2" {...F} />
    </>
  ),
  rower: (
    <>
      <path d="M5 48H52M8 48V55M50 48V55" />
      <circle cx="52" cy="40" r="8" {...F} />
      <rect x="14" y="43" width="12" height="5" rx="2.5" {...F} />
      <rect x="37" y="39" width="4" height="9" rx="1" />
      <path d="M44 33H38M44 33L48 37" />
    </>
  ),
  bike: (
    <>
      <circle cx="44" cy="44" r="10" {...F} />
      <path d="M16 56H54M22 56L26 22M19 22H31M26 35L44 44M44 44L48 16M43 16H55" />
    </>
  ),
  elliptical: (
    <>
      <path d="M6 56H58" />
      <circle cx="50" cy="45" r="8" {...F} />
      <path d="M12 48L46 41" />
      <rect x="16" y="43" width="11" height="4" rx="2" {...F} />
      <path d="M30 43L24 8M20 8H28M50 45V22" />
      <rect x="45" y="15" width="11" height="7" rx="2" {...F} />
    </>
  ),
};

export function EquipmentArt({ id, size = 56 }: { id: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ART[id] ?? <circle cx="32" cy="32" r="12" {...F} />}
    </svg>
  );
}

export const HAS_ART = (id: string): boolean => id in ART;
