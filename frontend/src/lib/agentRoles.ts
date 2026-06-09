import type { AgentId } from '../types/agents';

export interface AgentRole {
  id: AgentId;
  mono: string;
  name: string;
  no: string;
  fn: string;
  col: string; // 身份色三档(指向 CSS var)
  line: string;
  soft: string;
  avatar: string; // 本地头像路径
}

export const ROLES: Record<AgentId, AgentRole> = {
  collector: {
    id: 'collector',
    mono: '采',
    name: '采集员',
    no: 'RR-C01',
    fn: '证据采集',
    col: 'var(--id-collector)',
    line: 'var(--id-collector-line)',
    soft: 'var(--id-collector-soft)',
    avatar: '/agents/collector.svg',
  },
  analyst: {
    id: 'analyst',
    mono: '析',
    name: '分析员',
    no: 'RR-A01',
    fn: '对比分析',
    col: 'var(--id-analyst)',
    line: 'var(--id-analyst-line)',
    soft: 'var(--id-analyst-soft)',
    avatar: '/agents/analyst.svg',
  },
  writer: {
    id: 'writer',
    mono: '撰',
    name: '撰写员',
    no: 'RR-W01',
    fn: '报告撰写',
    col: 'var(--id-writer)',
    line: 'var(--id-writer-line)',
    soft: 'var(--id-writer-soft)',
    avatar: '/agents/writer.svg',
  },
  qc: {
    id: 'qc',
    mono: '质',
    name: '质检员',
    no: 'RR-Q01',
    fn: '质量校验',
    col: 'var(--id-qc)',
    line: 'var(--id-qc-line)',
    soft: 'var(--id-qc-soft)',
    avatar: '/agents/qc.svg',
  },
};

export const ROLE_ORDER: AgentId[] = ['collector', 'analyst', 'writer', 'qc'];

export const roleOf = (id: string): AgentRole | null => (ROLES as Record<string, AgentRole>)[id] ?? null;
