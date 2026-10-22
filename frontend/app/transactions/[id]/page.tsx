import ProofPayApp from "@/src/components/proofpay-app";
export default async function CasePage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <ProofPayApp section="case" transactionId={id} />; }
