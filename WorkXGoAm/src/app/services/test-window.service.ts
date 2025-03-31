import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class TestWindowService {

  constructor() { }

  getTestData(): string {
    return 'Data from TestWindowService';
  }
} 