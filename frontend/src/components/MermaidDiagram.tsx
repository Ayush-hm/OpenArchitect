import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    fontFamily: "Inter, ui-sans-serif, system-ui",
    primaryColor: "#eef4ee",
    primaryTextColor: "#172027",
    primaryBorderColor: "#8aa798",
    lineColor: "#5c7468",
    secondaryColor: "#f7f8f6",
    tertiaryColor: "#fff",
  },
});

type MermaidDiagramProps = {
  chart: string;
};

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const id = useId().replaceAll(":", "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    mermaid
      .render(`diagram-${id}`, chart)
      .then(({ svg: rendered }) => {
        if (!cancelled) {
          setSvg(rendered);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSvg("");
          setError(err instanceof Error ? err.message : "Unable to render diagram");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (error) {
    return (
      <pre className="diagram-fallback">
        {error}
        {"\n\n"}
        {chart}
      </pre>
    );
  }

  return <div className="diagram-surface" dangerouslySetInnerHTML={{ __html: svg }} />;
}
