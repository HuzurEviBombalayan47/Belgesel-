import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import { apiGet } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { ProjectSummary } from "@/lib/types";
import Header from "@/components/Header";
import UploadCard from "@/components/UploadCard";
import ProjectCard from "@/components/ProjectCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Hero plate: vintage projector, per the documentary art direction.
const HERO_IMAGE =
  "https://images.unsplash.com/photo-1779696304953-a4d28917f7fe?crop=entropy&cs=srgb&fm=jpg&q=85&ixlib=rb-4.1.0";

const CAPABILITIES = [
  "WHISPER TRANSCRIPT · TIMESTAMPS",
  "R2 OBJECT STORAGE",
  "AI SCENE PLANNING",
  "MULTI-LANE TIMELINE",
];

export default function Home() {
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiGet<ProjectSummary[]>("/projects"),
    refetchInterval: 10_000, // keeps transcription badges fresh while you sit on this page
  });
  const projects = projectsQuery.data;

  return (
    <div className="flex min-h-svh flex-col">
      <Header />

      {/* hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${HERO_IMAGE})` }}
          aria-hidden
        />
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(180deg, rgba(9,11,14,0.82) 0%, rgba(9,11,14,0.96) 78%)" }}
          aria-hidden
        />
        <div className="relative mx-auto w-full max-w-[1400px] px-4 py-14 sm:px-6 lg:py-20">
          <p className="font-mono text-[11px] tracking-[0.28em] text-gold" data-testid="hero-eyebrow">
            STAGE 2 · AI SCENE PLANNING
          </p>
          <h1
            className="mt-4 max-w-2xl font-heading text-4xl font-semibold leading-[1.05] tracking-tight text-white sm:text-5xl"
            data-testid="hero-title"
          >
            One recording in.
            <br />
            A documentary timeline out.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-300" data-testid="hero-copy">
            Upload a narration — Chronicle stores it in your Cloudflare R2 bucket, transcribes
            the speech with timestamps, then an AI visual director plans every scene: archival
            photos, maps, charts, kinetic type, the words worth emphasising.
          </p>
          <ul className="mt-7 flex flex-wrap gap-2" data-testid="hero-capabilities">
            {CAPABILITIES.map((item) => (
              <li
                key={item}
                className="rounded-full border border-amber-500/30 bg-[#78350F]/60 px-3 py-1 font-mono text-[10px] tracking-[0.14em] text-amber-100"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-12 px-4 py-10 sm:px-6">
        {/* upload */}
        <section className="mx-auto w-full max-w-3xl space-y-4" data-testid="upload-section">
          <div className="space-y-1">
            <h2 className="font-heading text-2xl font-semibold tracking-tight text-foreground">
              Start a new documentary
            </h2>
            <p className="text-sm text-muted-foreground">
              One audio file per project — a narration, an interview, a voiceover.
            </p>
          </div>
          <UploadCard />
        </section>

        {/* projects */}
        <section className="space-y-4" data-testid="projects-section">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-2xl font-semibold tracking-tight text-foreground">
              Your projects
            </h2>
            <span className="font-mono text-xs text-muted-foreground" data-testid="projects-count">
              {projects ? `${projects.length} total` : ""}
            </span>
          </div>

          {projectsQuery.isError ? (
            <div
              className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
              data-testid="projects-error"
            >
              <span className="flex items-center gap-2">
                <TriangleAlert className="size-4" />
                {errorMessage(projectsQuery.error)}
              </span>
              <Button variant="outline" size="sm" onClick={() => projectsQuery.refetch()} data-testid="projects-retry-button">
                <RefreshCw className="size-3.5" />
                Retry
              </Button>
            </div>
          ) : projectsQuery.isPending ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="projects-skeleton">
              {[0, 1, 2].map((key) => (
                <div key={key} className="h-40 animate-pulse rounded-xl border border-border bg-card/60" />
              ))}
            </div>
          ) : projects && projects.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="projects-list">
              {projects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          ) : (
            <Card className="border-dashed" data-testid="projects-empty">
              <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
                <Loader2 className="hidden" />
                <p className="font-heading text-base text-foreground">No projects yet</p>
                <p className="max-w-sm text-sm text-muted-foreground">
                  Upload your first narration above — its timeline, waveform and transcript
                  will appear here.
                </p>
              </CardContent>
            </Card>
          )}
        </section>
      </main>

      <footer className="border-t border-border/70 py-6" data-testid="footer-note">
        <p className="mx-auto max-w-[1400px] px-4 font-mono text-[10px] tracking-[0.18em] text-muted-foreground sm:px-6">
          CHRONICLE AI · AUDIO → TRANSCRIPT → AI SCENE PLAN — ASSET SEARCH & RENDERING ARRIVE NEXT
        </p>
      </footer>
    </div>
  );
}
