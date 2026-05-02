import { useParams } from "react-router-dom";

export default function ContractorPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div>
      <h1>Contractor</h1>
      <p>id: {id}</p>
      <p>Contractor detail coming in PR 10.3</p>
    </div>
  );
}
