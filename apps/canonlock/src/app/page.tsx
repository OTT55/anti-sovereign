import { FoldSequence } from "./_components/FoldSequence";
import { LedgerHead } from "./_components/LedgerHead";
import { ProofClaims } from "./_components/ProofClaims";
import { RegisterForm } from "./_components/RegisterForm";
import { TimestampNote } from "./_components/TimestampNote";

export default function HomePage() {
  return (
    <>
      <LedgerHead />
      <FoldSequence />
      <ProofClaims />
      <TimestampNote />
      <RegisterForm />
    </>
  );
}
