import { z } from 'zod';
import { api } from '../api/client';
import { McpCall, TokenStats, ContextPreview } from '../api/schemas';

const nul = <T extends z.ZodTypeAny>(t: T) => t.nullish().transform((v) => v ?? undefined);

export const WsMember = z
  .object({
    id: z.string(),
    name: z.string(),
    role: z.string(),
    team_id: z.string(),
    client: z.string(),
    device: z.string(),
    token_prefix: nul(z.string()),
    created_at: z.number(),
    status: z.enum(['online', 'idle', 'offline']),
    last_seen: nul(z.number()),
    calls: z.number(),
    tokens_saved: z.number(),
  })
  .passthrough();

export const WsView = z
  .object({
    org: z.string(),
    plan: z.string(),
    hub: z.string(),
    limits: z.object({ seats: z.number(), teams: z.number(), label: z.string(), note: z.string() }),
    teams: z.array(z.object({ id: z.string(), name: z.string(), seats: z.number() })),
    members: z.array(WsMember),
    links: z.array(z.object({ id: z.string(), a: z.string(), b: z.string(), scope: z.string(), paused: z.boolean(), created_at: z.number().optional() })),
    issued: nul(z.object({ member: WsMember.partial().passthrough(), token: z.string() })),
  })
  .passthrough();
export type WsView = z.infer<typeof WsView>;

const human = { role: 'human' as const };

export const getWorkspace = () => api(WsView, 'GET', 'workspace');
export const patchWorkspace = (body: { org?: string; plan?: string; hub?: string }) => api(WsView, 'PUT', 'workspace', { ...human, body });
export const addTeam = (name: string, seats: number) => api(WsView, 'POST', 'workspace/teams', { ...human, body: { name, seats } });
export const setSeats = (id: string, seats: number) => api(WsView, 'PATCH', `workspace/teams/${encodeURIComponent(id)}`, { ...human, body: { seats } });
export const removeTeam = (id: string) => api(WsView, 'DELETE', `workspace/teams/${encodeURIComponent(id)}`, human);
export const addMember = (m: { name: string; role: string; team_id: string; client: string; device: string }) => api(WsView, 'POST', 'workspace/members', { ...human, body: m });
export const rotateMember = (id: string) => api(WsView, 'POST', `workspace/members/${encodeURIComponent(id)}/rotate`, human);
export const removeMember = (id: string) => api(WsView, 'DELETE', `workspace/members/${encodeURIComponent(id)}`, human);
export const addLink = (a: string, b: string, scope: string) => api(WsView, 'POST', 'workspace/links', { ...human, body: { a, b, scope } });
export const pauseLink = (id: string, paused: boolean) => api(WsView, 'PATCH', `workspace/links/${encodeURIComponent(id)}`, { ...human, body: { paused } });
export const removeLink = (id: string) => api(WsView, 'DELETE', `workspace/links/${encodeURIComponent(id)}`, human);

export const getActivity = (memberId?: string) => api(z.array(McpCall), 'GET', 'mcp/activity', { query: { limit: 150, member_id: memberId } });
export const getTokenStats = () => api(TokenStats, 'GET', 'token-stats');
export const getContextPreview = (query: string, budget: number) => api(ContextPreview, 'GET', 'context/preview', { query: { query, budget } });
