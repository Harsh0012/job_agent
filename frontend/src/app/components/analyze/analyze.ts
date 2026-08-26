import { Component, signal, computed, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { jsPDF } from 'jspdf';
import { ApiService } from '../../services/api';
import { AnalysisResult } from '../../models/analysis.model';

@Component({
  selector: 'app-analyze',
  imports: [CommonModule, FormsModule],
  templateUrl: './analyze.html',
  styleUrl: './analyze.scss'
})
export class Analyze implements OnDestroy {
  resumeFile: File | null = null;
  jobDescription = '';
  numQuestions = 10;
  result = signal<AnalysisResult | null>(null);
  loading = signal(false);
  error = signal('');
  viewMode = signal<'candidate' | 'recruiter'>('candidate');
  activeTab = signal<'gaps' | 'tailored' | 'cover' | 'questions' | 'recruiter'>('gaps');
  copySuccess = signal(false);
  pipelineStep = signal(0);
  dragOver = signal(false);

  private readonly MAX_FILE_SIZE = 5 * 1024 * 1024;
  private readonly ALLOWED_TYPES = ['application/pdf', 'text/plain'];
  private streamController: AbortController | null = null;

  // Maps backend node names to pipeline step indices
  private readonly nodeStepMap: Record<string, number> = {
    parse_resume: 0,
    analyze_jd: 1,
    gap_analysis: 2,
    tailor_resume: 3,
    generate_cover_letter: 4,
    generate_interview_qs: 5,
  };

  readonly pipelineSteps = [
    { label: 'Parsing Resume', icon: '📄' },
    { label: 'Analyzing JD', icon: '🔍' },
    { label: 'Gap Analysis', icon: '🎯' },
    { label: 'Tailoring Resume', icon: '✍️' },
    { label: 'Cover Letter', icon: '📝' },
    { label: 'Interview Qs', icon: '💬' },
  ];

  readonly matchPct = computed(() => {
    const r = this.result();
    if (!r) return 0;
    const reqs = r.jd_data.requirements;
    if (!reqs.length) return 100;

    // ATS weighted scoring: must-have = 3x weight, nice-to-have = 1x
    let totalWeight = 0;
    let metWeight = 0;
    const gapSkills = new Set(r.gaps.map(g => g.requirement.toLowerCase()));

    for (const req of reqs) {
      const weight = req.importance === 'must-have' ? 3 : 1;
      totalWeight += weight;
      if (!gapSkills.has(req.skill.toLowerCase())) {
        metWeight += weight;
      }
    }

    return totalWeight > 0 ? Math.round((metWeight / totalWeight) * 100) : 100;
  });

  constructor(private api: ApiService) {}

  ngOnDestroy(): void {
    this.streamController?.abort();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    this.onFileSelected(event);
  }

  onFileSelected(event: Event): void {
    let file: File | undefined;
    const dragEvent = event as DragEvent;
    if (dragEvent.dataTransfer?.files?.length) {
      file = dragEvent.dataTransfer.files[0];
    } else {
      const input = event.target as HTMLInputElement;
      file = input.files?.[0];
    }
    if (!file) return;

    if (!this.ALLOWED_TYPES.includes(file.type)) {
      this.error.set('Unsupported file type. Please upload a PDF or TXT file.');
      this.resumeFile = null;
      return;
    }
    if (file.size > this.MAX_FILE_SIZE) {
      this.error.set('File is too large. Maximum size is 5 MB.');
      this.resumeFile = null;
      return;
    }
    this.error.set('');
    this.resumeFile = file;
  }

  removeFile(): void {
    this.resumeFile = null;
  }

  onSubmit(): void {
    if (!this.resumeFile) {
      this.error.set('Please upload a resume file.');
      return;
    }
    if (!this.jobDescription.trim()) {
      this.error.set('Please enter a job description.');
      return;
    }

    this.loading.set(true);
    this.error.set('');
    this.result.set(null);
    this.pipelineStep.set(-1);

    this.streamController = this.api.analyzeStream(
      this.resumeFile,
      this.jobDescription,
      this.numQuestions,
      (step) => {
        const idx = this.nodeStepMap[step.node];
        if (idx !== undefined) {
          this.pipelineStep.set(idx);
        }
      },
      (result) => {
        this.pipelineStep.set(this.pipelineSteps.length - 1);
        this.result.set(result);
        this.loading.set(false);
      },
      (errorMsg) => {
        this.error.set(errorMsg);
        this.loading.set(false);
      },
    );
  }

  setTab(tab: 'gaps' | 'tailored' | 'cover' | 'questions' | 'recruiter'): void {
    this.activeTab.set(tab);
  }

  toggleViewMode(): void {
    const next = this.viewMode() === 'candidate' ? 'recruiter' : 'candidate';
    this.viewMode.set(next);
    this.activeTab.set(next === 'recruiter' ? 'gaps' : 'gaps');
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text).then(() => {
      this.copySuccess.set(true);
      setTimeout(() => this.copySuccess.set(false), 2000);
    });
  }

  downloadAsText(content: string, filename: string): void {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  resetAnalysis(): void {
    this.streamController?.abort();
    this.streamController = null;
    this.result.set(null);
    this.error.set('');
    this.resumeFile = null;
    this.jobDescription = '';
    this.numQuestions = 10;
    this.loading.set(false);
    this.pipelineStep.set(0);
    this.activeTab.set('gaps');
    this.viewMode.set('candidate');
  }

  exportPdf(): void {
    const r = this.result();
    if (!r) return;

    const doc = new jsPDF();
    const margin = 15;
    const pageWidth = doc.internal.pageSize.getWidth() - margin * 2;
    let y = 20;

    const addText = (text: string, fontSize = 10, bold = false) => {
      doc.setFontSize(fontSize);
      doc.setFont('helvetica', bold ? 'bold' : 'normal');
      const lines = doc.splitTextToSize(text, pageWidth);
      for (const line of lines) {
        if (y > 275) { doc.addPage(); y = 20; }
        doc.text(line, margin, y);
        y += fontSize * 0.5;
      }
      y += 3;
    };

    const addSection = (title: string) => {
      y += 5;
      if (y > 265) { doc.addPage(); y = 20; }
      addText(title, 14, true);
      y += 2;
    };

    // Header
    addText('Job Application Analysis Report', 18, true);
    addText(`Candidate: ${r.resume_data.name}`, 11);
    addText(`Position: ${r.jd_data.title} at ${r.jd_data.company}`, 11);
    addText(`Match Score: ${this.matchPct()}% (ATS Weighted)`, 11);
    addText(`Generated: ${new Date().toLocaleDateString()}`, 9);

    // Gaps
    addSection('Skill Gaps');
    if (r.gaps.length === 0) {
      addText('No gaps identified — strong match!');
    } else {
      for (const gap of r.gaps) {
        addText(`• [${gap.importance}] ${gap.requirement}: ${gap.assessment}`);
      }
    }

    // Strengths
    addSection('Strengths');
    const gapSkills = new Set(r.gaps.map(g => g.requirement.toLowerCase()));
    const strengths = r.jd_data.requirements
      .filter(req => !gapSkills.has(req.skill.toLowerCase()))
      .map(req => req.skill);
    for (const s of strengths) { addText(`• ${s}`); }

    // Tailored Bullets
    if (r.tailored_bullets.length > 0) {
      addSection('Tailored Resume Bullets');
      for (const b of r.tailored_bullets) {
        addText(`Gap: ${b.gap_addressed}`, 9);
        addText(`  → ${b.tailored}`);
      }
    }

    // Cover Letter
    addSection('Cover Letter');
    addText(r.cover_letter);

    // Interview Questions
    addSection('Interview Questions');
    r.interview_questions.forEach((q, i) => {
      addText(`${i + 1}. ${q}`);
    });

    doc.save(`analysis-${r.jd_data.company.replace(/\s+/g, '-').toLowerCase()}.pdf`);
  }
}
