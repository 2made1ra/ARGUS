import { useParams } from "react-router-dom";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div>
      <h1>Document</h1>
      <p>id: {id}</p>
      <p>Document detail coming in PR 10.2</p>
    </div>
  );
}
