export type DocumentFixture = {
  documentType: "LOAN" | "INSURANCE" | "MEDICAL" | "ONBOARDING";
  filename: string;
  mimeType: "application/pdf";
  content: Buffer;
  fields: Record<string, string | null>;
};

const defaultFields: Record<DocumentFixture["documentType"], Record<string, string | null>> = {
  LOAN: {
    applicant_name: "Jordan Rivera",
    ssn: "000-00-0000",
    loan_amount: "$45,000.00",
    application_date: "2026-01-15",
    employer: "Contoso Manufacturing"
  },
  INSURANCE: {
    policy_number: "AB-1234567",
    insured_name: "Sam Okafor",
    effective_date: "2026-02-01",
    claim_amount: "$1,250.00"
  },
  MEDICAL: {
    patient_mrn: "MRN1234567",
    patient_name: "Alex Chen",
    date_of_service: "2026-01-20",
    provider_npi: "1234567890"
  },
  ONBOARDING: {
    full_name: "Priya Nair",
    start_date: "2026-03-01",
    email: "priya.nair@example.com",
    id_document_number: "X1234567"
  }
};

export function documentFixtureFactory(
  overrides: Partial<Omit<DocumentFixture, "content" | "fields">> & {
    fields?: Record<string, string | null>;
    confidences?: Record<string, number>;
    uniqueSuffix?: string;
  } = {}
): DocumentFixture {
  const documentType = overrides.documentType ?? "LOAN";
  const fields = overrides.fields ?? defaultFields[documentType];
  const suffix = overrides.uniqueSuffix ?? Date.now();
  const filename = overrides.filename ?? `smoke-${documentType.toLowerCase()}-${suffix}.pdf`;
  const fixtureBlock = JSON.stringify({
    fields,
    confidences: overrides.confidences ?? Object.fromEntries(Object.keys(fields).map((key) => [key, 0.95]))
  });
  const content = Buffer.from(
    `%PDF-1.4\n% SecureDox test fixture ${suffix}\nSECUREDOX-FIXTURE:${fixtureBlock}\n%%EOF\n`
  );

  return {
    documentType,
    filename,
    mimeType: overrides.mimeType ?? "application/pdf",
    content,
    fields
  };
}
