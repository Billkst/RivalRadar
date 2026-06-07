import type { SyntheticEvent } from 'react';
import type { AgentId } from '../types/agents';
import { ROLES } from './agentRoles';

export const avatarSrc = (id: AgentId): string => ROLES[id].avatar;

// img onError handler:隐藏 broken img,露父级身份色底纹
// (父 div 已设 background:var(--idc-soft))。
export const onAvatarError = (e: SyntheticEvent<HTMLImageElement>) => {
  e.currentTarget.style.display = 'none';
};
