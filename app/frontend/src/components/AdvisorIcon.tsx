import type { IconProps } from "@tabler/icons-react";
import {
  IconMoodBoy,
  IconMoodConfuzed,
  IconMoodCrazyHappy,
  IconMoodEdit,
  IconMoodEmpty,
  IconMoodKid,
  IconMoodLookLeft,
  IconMoodLookRight,
  IconMoodNerd,
  IconMoodPuzzled,
  IconMoodSadDizzy,
  IconMoodSilence,
  IconMoodSmile,
  IconMoodSmileBeam,
  IconMoodSmileDizzy,
  IconMoodSuprised,
  IconMoodTongueWink2,
  IconMoodWink2,
  IconUser,
} from "@tabler/icons-react";
import type { ComponentType } from "react";

interface AdvisorIconProps {
  advisorId: string;
  tablerIcon?: string;
  className?: string;
  size?: number;
  stroke?: number;
}

type IconComponent = ComponentType<IconProps>;

const FACE_ICONS: IconComponent[] = [
  IconMoodSmile,
  IconMoodWink2,
  IconMoodCrazyHappy,
  IconMoodSmileBeam,
  IconMoodConfuzed,
  IconMoodLookLeft,
  IconMoodLookRight,
  IconMoodPuzzled,
  IconMoodTongueWink2,
  IconMoodEmpty,
  IconMoodSadDizzy,
  IconMoodNerd,
  IconMoodSilence,
  IconMoodSuprised,
  IconMoodBoy,
  IconMoodKid,
  IconMoodSmileDizzy,
  IconMoodEdit,
];

const ICON_BY_NAME: Record<string, IconComponent> = {
  IconMoodSmile,
  IconMoodWink2,
  IconMoodCrazyHappy,
  IconMoodSmileBeam,
  IconMoodConfuzed,
  IconMoodLookLeft,
  IconMoodLookRight,
  IconMoodPuzzled,
  IconMoodTongueWink2,
  IconMoodEmpty,
  IconMoodSadDizzy,
  IconMoodNerd,
  IconMoodSilence,
  IconMoodSuprised,
  IconMoodBoy,
  IconMoodKid,
  IconMoodSmileDizzy,
  IconMoodEdit,
  IconUser,
};

function hash(value: string): number {
  return value
    .split("")
    .reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 7);
}

function resolveIcon(advisorId: string, tablerIcon?: string): IconComponent {
  if (typeof tablerIcon === "string" && tablerIcon.trim() !== "") {
    const explicitIcon = ICON_BY_NAME[tablerIcon.trim()];
    if (explicitIcon !== undefined) {
      return explicitIcon;
    }
  }

  if (FACE_ICONS.length > 0) {
    const index = hash(advisorId) % FACE_ICONS.length;
    return FACE_ICONS[index];
  }

  return IconUser;
}

export function AdvisorIcon(props: AdvisorIconProps): JSX.Element {
  const Icon = resolveIcon(props.advisorId, props.tablerIcon);
  return (
    <Icon
      aria-hidden="true"
      className={props.className}
      size={props.size ?? 22}
      stroke={props.stroke ?? 1.8}
    />
  );
}
