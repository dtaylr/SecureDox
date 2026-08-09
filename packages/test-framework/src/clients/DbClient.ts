import pg from "pg";
import type { Pool as PoolType } from "pg";

const { Pool } = pg;

export type AuditEventRow = {
  id: string;
  tenant_id: string;
  document_id: string | null;
  action: string;
  actor: string;
  correlation_id: string;
  detail: Record<string, unknown>;
  created_at: Date;
};

export type DocumentRow = {
  id: string;
  tenant_id: string;
  status: string;
  document_type: string;
  original_filename: string;
  correlation_id: string;
  processed_at: Date | null;
};

export class DbClient {
  private readonly pool: PoolType;

  constructor(
    connectionString =
      process.env.DATABASE_URL_SYNC ??
      process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://") ??
      "postgresql://securedox:securedox_local_pw@localhost:5432/securedox"
  ) {
    this.pool = new Pool({
      connectionString: connectionString.replace("postgresql+psycopg://", "postgresql://")
    });
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async getDocument(documentId: string): Promise<DocumentRow | null> {
    const result = await this.pool.query<DocumentRow>(
      `select id::text, tenant_id, status::text, document_type::text, original_filename,
              correlation_id, processed_at
         from documents
        where id = $1`,
      [documentId]
    );
    return result.rows[0] ?? null;
  }

  async auditEventsForDocument(documentId: string): Promise<AuditEventRow[]> {
    const result = await this.pool.query<AuditEventRow>(
      `select id::text, tenant_id, document_id::text, action::text, actor,
              correlation_id, detail, created_at
         from audit_events
        where document_id = $1
        order by created_at asc`,
      [documentId]
    );
    return result.rows;
  }

  async auditEventsByCorrelation(correlationId: string): Promise<AuditEventRow[]> {
    const result = await this.pool.query<AuditEventRow>(
      `select id::text, tenant_id, document_id::text, action::text, actor,
              correlation_id, detail, created_at
         from audit_events
        where correlation_id = $1
        order by created_at asc`,
      [correlationId]
    );
    return result.rows;
  }
}
