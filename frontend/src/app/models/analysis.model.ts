export interface AnalysisResult {
  cached: boolean;
  resume_data: ResumeData;
  jd_data: JDData;
  gaps: Gap[];
  candidate_score: number;
  recruiter_insights: RecruiterInsights;
  tailored_bullets: TailoredBullet[];
  cover_letter: string;
  interview_questions: string[];
}

export interface ResumeData {
  name: string;
  skills: string[];
  experience: Experience[];
  education: Education[];
  summary: string;
}

export interface Experience {
  company: string;
  role: string;
  duration: string;
  bullets: string[];
}

export interface Education {
  institution: string;
  degree: string;
  year: string;
}

export interface JDData {
  title: string;
  company: string;
  requirements: JDRequirement[];
  responsibilities: string[];
  experience_years: string;
}

export interface JDRequirement {
  skill: string;
  importance: string;
}

export interface Gap {
  requirement: string;
  importance: string;
  assessment: string;
}

export interface RecruiterInsights {
  hiring_risks: string[];
  recommendation: string;
  justification: string;
}

export interface TailoredBullet {
  original: string;
  tailored: string;
  gap_addressed: string;
}
