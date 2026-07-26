import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timeout, retry, timer } from 'rxjs';
import { AnalysisResult } from '../models/analysis.model';
import { environment } from '../../environments/environment';

export interface SSEStepEvent {
  node: string;
  status: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  analyze(resumeFile: File, jobDescription: string, numQuestions: number = 10): Observable<AnalysisResult> {
    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('job_description', jobDescription);
    formData.append('num_questions', numQuestions.toString());
    return this.http.post<AnalysisResult>(`${this.baseUrl}/analyze`, formData).pipe(
      timeout(120_000),
      retry({ count: 1, delay: (_, retryCount) => timer(retryCount * 3000) }),
    );
  }

  analyzeStream(
    resumeFile: File,
    jobDescription: string,
    numQuestions: number,
    onStep: (event: SSEStepEvent) => void,
    onResult: (result: AnalysisResult) => void,
    onError: (error: string) => void,
  ): AbortController {
    const controller = new AbortController();
    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('job_description', jobDescription);
    formData.append('num_questions', numQuestions.toString());

    fetch(`${this.baseUrl}/analyze/stream`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({ detail: 'Request failed' }));
          onError(body.detail || `Server error ${response.status}`);
          return;
        }
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop()!; // keep incomplete chunk

          for (const part of parts) {
            if (!part.trim()) continue;
            const lines = part.split('\n');
            let eventType = '';
            let data = '';
            for (const line of lines) {
              if (line.startsWith('event: ')) eventType = line.slice(7);
              else if (line.startsWith('data: ')) data = line.slice(6);
            }
            if (eventType === 'step') {
              onStep(JSON.parse(data));
            } else if (eventType === 'result') {
              onResult(JSON.parse(data));
            } else if (eventType === 'error') {
              onError(JSON.parse(data).detail);
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError('Cannot reach the server. Make sure the API is running on port 8000.');
        }
      });

    return controller;
  }

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>(`${this.baseUrl}/health`).pipe(
      timeout(5000),
    );
  }
}
