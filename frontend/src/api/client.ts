import { z } from 'zod';
import { devLog } from './devlog';
import { ErrorBody } from './schemas';
import { mockBackend } from '../mocks/backend';

export const API_MODE: 'mock' | 'live' = import.meta.env.VITE_API_MODE === 'live' ? 'live' : 'mock';

export type Role = 'human' | 'auditor' | 'agent';

interface RuntimeConfig {
  tokens: Record<string, Partial<Record<Role, string>>>;
  tenants: string[];
}

let config: RuntimeConfig = { tokens: {}, tenants: [] };
export const session = { tenant: 'acme', role: 'human' as Role };

/** Throwaway tokens for the in-browser sample backend. They grant nothing anywhere else. */
const MOCK_CONFIG: RuntimeConfig = {
  tokens: {
    acme: { human: 'mock-acme-human', auditor: 'mock-acme-auditor', agent: 'mock-acme-agent' },
    globex: { human: 'mock-globex-human', auditor: 'mock-globex-auditor', agent: 'mock-globex-agent' },
  },
  tenants: ['acme', 'globex'],
};

export async function loadConfig(): Promise<RuntimeConfig> {
  if (API_MODE === 'mock') {
    config = MOCK_CONFIG;
  } else {
    try {
      const res = await fetch('/config.json', { cache: 'no-store' });
      if (res.ok) config = (await res.json()) as RuntimeConfig;
      else devLog('warn', 'No /config.json found. Copy public/config.example.json and add tokens.', true);
    } catch {
      devLog('warn', 'Could not read /config.json; no tokens available.', true);
    }
  }
  if (config.tenants.length === 0) config.tenants = Object.keys(config.tokens);
  const first = config.tenants[0];
  if (first && !(session.tenant in config.tokens)) session.tenant = first;
  return config;
}

export const tenants = () => config.tenants;

export function tokenFor(role: Role = session.role): string | null {
  return config.tokens[session.tenant]?.[role] ?? null;
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly endpoint: string,
    readonly field?: string,
  ) {
    super(message);
  }
}

interface Opts {
  query?: Record<string, string | number | undefined>;
  body?: unknown;
  role?: Role;
}

export async function api<T>(
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  method: 'GET' | 'POST',
  path: string,
  opts: Opts = {},
): Promise<T> {
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined) query.set(k, String(v));
  const endpoint = `${method} ${path}`;
  const token = tokenFor(opts.role);
  let status: number;
  let json: unknown;

  if (API_MODE === 'mock') {
    await new Promise((r) => setTimeout(r, 30));
    const r = mockBackend.handle({ method, path, query, body: opts.body ?? null, token });
    status = r.status;
    json = JSON.parse(JSON.stringify(r.body));
  } else {
    const qs = query.toString();
    let res: Response;
    try {
      res = await fetch(`/api/${path.replace(/^\/+/, '')}${qs ? `?${qs}` : ''}`, {
        method,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(opts.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        },
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
    } catch {
      throw new ApiError('UNREACHABLE', 'unreachable', 0, endpoint);
    }
    status = res.status;
    try {
      json = await res.json();
    } catch {
      json = null;
    }
  }

  if (status >= 400) {
    const parsed = ErrorBody.safeParse(json);
    const e = parsed.success ? parsed.data.error : { code: 'INTERNAL', message: `HTTP ${status}` };
    devLog('warn', `${endpoint} -> ${status} ${e.code}`);
    throw new ApiError(e.code, e.message, status, endpoint);
  }

  const out = schema.safeParse(json);
  if (!out.success) {
    const issue = out.error.issues[0];
    const field = issue ? issue.path.join('.') || '(root)' : '(unknown)';
    devLog('error', `${endpoint} failed validation at ${field}: ${issue?.message ?? ''}`);
    throw new ApiError('SCHEMA', 'schema', status, endpoint, field);
  }
  return out.data;
}
