/**
 * LearnMate AI - Mock Datasets
 * Academic Title: "AI-Powered Personalized Learning Content Generator"
 */

const LearnMateData = {
  // Current Student Profile (Synchronized dynamically via LearnMateAPI from MySQL)
  currentUser: {
    fullName: "Student",
    email: "",
    avatarInitial: "ST",
    preferences: ["Visual Learning", "Step-by-Step"],
    primaryFocus: "Visual Learning",
    pace: "Intermediate",
    studyHours: 0,
    sessionsCompleted: 0,
    quizzesTaken: 0,
    averageScore: "0.0%"
  },

  // Generated Content For Default Topic: CPU Scheduling Algorithms
  activeTopic: {
    title: "CPU Scheduling: Round Robin & FCFS Algorithms",
    category: "Operating Systems",
    generatedAt: "Today, 10:45 AM",
    preferenceFocus: "Visual & Step-by-Step",
    
    // 1. Simplified Notes
    simplifiedNotes: {
      keyIdea: "CPU scheduling determines which process in the ready queue gets allocated the CPU, balancing throughput, latency, and turnaround time.",
      points: [
        { title: "FCFS (First-Come, First-Served)", text: "Non-preemptive algorithm that allocates the CPU in order of arrival. Simple but suffers from the Convoy Effect (short processes waiting behind long ones)." },
        { title: "Round Robin (RR)", text: "Preemptive algorithm designed for time-sharing systems. Allocates a fixed time slice (Time Quantum). When expired, the process goes to the back of the ready queue." },
        { title: "Turnaround Time (TAT)", text: "Completion Time minus Arrival Time. Represents total time elapsed from submission to completion." },
        { title: "Waiting Time (WT)", text: "Turnaround Time minus Burst Time. Represents time spent idling in the ready queue." },
        { title: "Crucial Rule of Quantum", text: "If time quantum q is extremely large, RR degenerates to FCFS. If q is very small, overhead from context switching dominates." }
      ]
    },

    // 2. Detailed Explanations
    detailedExplanation: [
      {
        heading: "1. Understanding CPU Scheduling Fundamentals",
        content: "In modern multiprogramming operating systems, the CPU scheduler (also called the short-term scheduler) selects from among the processes in memory that are ready to execute and allocates the CPU to one of them. The goal is to maximize CPU utilization and throughput while minimizing waiting time, turnaround time, and response time."
      },
      {
        heading: "2. First-Come, First-Served (FCFS) In-Depth",
        content: "Under FCFS, processes are executed strictly in order of arrival using a FIFO queue. It is inherently non-preemptive: once a process gains the CPU, it keeps it until it terminates or requests I/O. A major disadvantage is the Convoy Effect: if a CPU-bound process with a huge burst time arrives before several quick I/O-bound tasks, all subsequent tasks are severely delayed, leading to low resource utilization."
      },
      {
        heading: "3. Round Robin (RR) & The Time Quantum Trade-off",
        content: "Round Robin introduces preemption via a hardware timer. Each process gets a unit of CPU time called a time quantum (typically 10 to 100 milliseconds). If the process burst exceeds the quantum, an interrupt triggers a context switch, moving the active process to the tail of the ready queue. The selection of the time quantum is critical: 80% of CPU bursts should typically be shorter than the quantum to avoid excessive context-switching overhead."
      }
    ],

    // 3. Step-by-Step Explanations
    stepByStep: [
      {
        step: 1,
        title: "Process Arrival & Ready Queue Initialization",
        desc: "Processes P1 (burst 24ms), P2 (burst 3ms), and P3 (burst 3ms) arrive simultaneously at time t = 0ms into the ready queue.",
        reason: "Initial state setup to establish the sequence of execution."
      },
      {
        step: 2,
        title: "Allocate First Time Quantum (q = 4ms)",
        desc: "P1 is dispatched. It executes for 4ms. Remaining burst for P1 becomes 20ms. The timer interrupts and preempts P1.",
        reason: "Preemption enforces fairness and prevents any single process from monopolizing the core."
      },
      {
        step: 3,
        title: "Context Switch to P2 and P3",
        desc: "P2 executes for its full 3ms burst and finishes at t = 7ms. Next, P3 executes for its full 3ms burst and finishes at t = 10ms.",
        reason: "Short processes finish rapidly in Round Robin, yielding dramatically lower response times than FCFS."
      },
      {
        step: 4,
        title: "Complete Remaining Bursts for P1",
        desc: "With P2 and P3 complete, P1 runs uninterrupted through remaining quanta until finishing at t = 30ms.",
        reason: "Final turnaround time calculation: P1 = 30ms, P2 = 7ms, P3 = 10ms. Average TAT = 15.67ms."
      }
    ],

    // 4. Summaries
    summary: {
      takeaway: "Round Robin provides superior interactive responsiveness and eliminates starvation through preemptive time slicing, while FCFS is simpler with zero scheduling overhead but suffers from prolonged waiting times.",
      metrics: [
        { metric: "Preemption", fcfs: "No (Non-preemptive)", rr: "Yes (Timer interrupt)" },
        { metric: "Overhead", fcfs: "Minimal (No switches)", rr: "Moderate (Depends on quantum)" },
        { metric: "Starvation Risk", fcfs: "None", rr: "None" },
        { metric: "Best Suited For", fcfs: "Batch processing", rr: "Time-sharing / Interactive OS" }
      ]
    },

    // 5. Flashcards (Interactive Flip)
    flashcards: [
      { id: 1, front: "What is the Convoy Effect in CPU Scheduling?", back: "A situation in FCFS where short processes queue behind a long CPU-bound process, causing high average waiting time." },
      { id: 2, front: "How is Turnaround Time (TAT) calculated?", back: "Turnaround Time = Completion Time - Arrival Time (total time from submission to termination)." },
      { id: 3, front: "What happens if the Round Robin Time Quantum is set too high?", back: "Round Robin effectively degenerates into First-Come First-Served (FCFS) scheduling." },
      { id: 4, front: "What is the difference between Preemptive and Non-preemptive scheduling?", back: "Preemptive can interrupt a running process (e.g. RR, SRTF); Non-preemptive lets a process run until completion or voluntary I/O." },
      { id: 5, front: "Why is context switching cost significant in Round Robin?", back: "Saving/restoring registers and cache flushing consume CPU cycles; tiny quanta make this overhead disproportionately high." }
    ],

    // 6. Questions & Answers
    qaList: [
      {
        q: "Why is Round Robin particularly suitable for time-shared operating systems?",
        a: "Because it guarantees that every process receives a slice of CPU time within a bounded window (n-1) * q, ensuring swift response times for interactive users rather than forcing tasks to wait for preceding batch jobs to complete."
      },
      {
        q: "How does the choice of time quantum affect system throughput?",
        a: "If the quantum is too short, a large fraction of CPU cycles are wasted on register swapping, state saves, and pipeline invalidations. If too long, interactive tasks experience lag. The heuristic is to set quantum q slightly larger than 80% of typical CPU bursts."
      },
      {
        q: "Can starvation occur in basic Round Robin or FCFS scheduling?",
        a: "No. In FCFS, every process eventually reaches the front of the queue. In Round Robin, processes take turns cyclically, guaranteeing progress for every runnable thread."
      },
      {
        q: "Explain Waiting Time (WT) and its relationship with Turnaround Time.",
        a: "Waiting Time is the cumulative duration a process spends idle in the ready queue. Formula: Waiting Time = Turnaround Time - Burst Time."
      }
    ],

    // 7. Flowchart Diagram (Structured Definition for SVG Visualization)
    flowchart: {
      title: "Round Robin Scheduling Execution Cycle",
      steps: [
        { id: "new", label: "New Process Arrives", type: "start" },
        { id: "ready", label: "Enter Ready Queue", type: "process" },
        { id: "dispatch", label: "CPU Dispatches Process", type: "process" },
        { id: "check", label: "Burst <= Quantum?", type: "decision" },
        { id: "done", label: "Process Terminates", type: "end" },
        { id: "preempt", label: "Timer Interrupt (Preempt)", type: "process" }
      ]
    },

    // 8. Quiz
    quiz: {
      id: "cpu-sched-quiz-1",
      title: "CPU Scheduling Knowledge Check",
      questions: [
        {
          id: 1,
          question: "Which of the following algorithms is strictly non-preemptive?",
          options: ["Round Robin", "First-Come, First-Served (FCFS)", "Shortest Remaining Time First (SRTF)", "Priority Preemptive"],
          answer: 1,
          explanation: "In FCFS, once the CPU has been allocated to a process, the process keeps the CPU until it releases it, either by terminating or by requesting I/O."
        },
        {
          id: 2,
          question: "If the time quantum in Round Robin is made arbitrarily large, it behaves identically to which algorithm?",
          options: ["Shortest Job First", "FCFS", "Priority Scheduling", "Multilevel Feedback Queue"],
          answer: 1,
          explanation: "When the time quantum is larger than any process burst, no preemption ever fires, so processes run in strict arrival order (FCFS)."
        },
        {
          id: 3,
          question: "Turnaround time is mathematically defined as:",
          options: ["Burst Time + Waiting Time", "Completion Time - Arrival Time", "Waiting Time - Arrival Time", "Both A and B"],
          answer: 3,
          explanation: "Turnaround Time equals Completion Time - Arrival Time, which also equals Burst Time + Waiting Time."
        },
        {
          id: 4,
          question: "What is the primary cause of the Convoy Effect in FCFS?",
          options: ["High context switching frequency", "Short tasks stuck behind a lengthy CPU-bound task", "Hardware timer malfunctions", "Memory thrashing"],
          answer: 1,
          explanation: "The Convoy Effect occurs when a CPU-intensive job holds the processor while shorter, I/O-bound jobs wait helplessly behind it."
        }
      ]
    }
  },

  // Alternative Preset Topic: Binary Search Trees
  alternateTopic: {
    title: "Binary Search Trees: Operations & Traversal",
    category: "Data Structures & Algorithms",
    generatedAt: "Yesterday, 3:15 PM",
    preferenceFocus: "Step-by-Step & Practice",
    simplifiedNotes: {
      keyIdea: "A Binary Search Tree (BST) is a node-based binary tree data structure where the left subtree contains values smaller than the root, and the right subtree contains values greater.",
      points: [
        { title: "BST Property", text: "For every node X: Left subtree keys < X.key < Right subtree keys." },
        { title: "Search Complexity", text: "Average case: O(log n). Worst case (unbalanced degenerate tree): O(n)." },
        { title: "In-Order Traversal", text: "Visiting Left -> Root -> Right yields all keys in strictly sorted ascending order." },
        { title: "Deletion Cases", text: "0 children: simply remove; 1 child: splice node; 2 children: replace with in-order successor or predecessor." }
      ]
    }
  },

  // My Materials List
  materials: [
    {
      id: "mat-1",
      name: "Operating_Systems_Chapter3_CPU_Scheduling.pdf",
      type: "pdf",
      size: "2.4 MB",
      uploadDate: "Sep 14, 2026",
      topic: "CPU Scheduling Algorithms"
    },
    {
      id: "mat-2",
      name: "Data_Structures_Trees_and_Graphs.docx",
      type: "docx",
      size: "1.1 MB",
      uploadDate: "Sep 10, 2026",
      topic: "Binary Search Trees"
    },
    {
      id: "mat-3",
      name: "Cellular_Respiration_and_Metabolism.pptx",
      type: "pptx",
      size: "4.8 MB",
      uploadDate: "Sep 06, 2026",
      topic: "Cellular Respiration"
    },
    {
      id: "mat-4",
      name: "Database_Normalization_1NF_to_BCNF.pdf",
      type: "pdf",
      size: "1.8 MB",
      uploadDate: "Aug 29, 2026",
      topic: "Database Normalization"
    }
  ],

  // Learning History Sessions
  historySessions: [
    {
      id: "hist-1",
      topic: "CPU Scheduling Algorithms",
      date: "Sep 15, 2026",
      time: "10:45 AM",
      score: "40%",
      scoreStatus: "warning",
      resources: ["Simplified Notes", "Detailed", "Step-by-Step", "Summaries", "Flashcards", "Q&A", "Diagram", "Quiz"]
    },
    {
      id: "hist-2",
      topic: "Binary Search Trees & Balancing",
      date: "Sep 12, 2026",
      time: "04:20 PM",
      score: "92%",
      scoreStatus: "success",
      resources: ["Simplified Notes", "Detailed", "Flashcards", "Q&A", "Quiz"]
    },
    {
      id: "hist-3",
      topic: "Cellular Respiration & Krebs Cycle",
      date: "Sep 08, 2026",
      time: "02:15 PM",
      score: "85%",
      scoreStatus: "success",
      resources: ["Simplified Notes", "Step-by-Step", "Flashcards", "Diagram", "Quiz"]
    },
    {
      id: "hist-4",
      topic: "Database Normalization & BCNF",
      date: "Aug 31, 2026",
      time: "11:30 AM",
      score: "70%",
      scoreStatus: "info",
      resources: ["Simplified Notes", "Detailed", "Q&A", "Quiz"]
    },
    {
      id: "hist-5",
      topic: "Newton's Laws of Motion & Momentum",
      date: "Aug 22, 2026",
      time: "09:10 AM",
      score: "88%",
      scoreStatus: "success",
      resources: ["Simplified Notes", "Detailed", "Flashcards", "Diagram", "Quiz"]
    }
  ],

  // Performance Dashboard Data
  performance: {
    kpis: {
      topicsStudied: 18,
      quizzesAttempted: 24,
      averageScore: "78.5%",
      overallProgress: "84%"
    },
    topicBreakdown: [
      { topic: "Binary Search Trees", score: 92, status: "strong" },
      { topic: "Newtonian Mechanics", score: 88, status: "strong" },
      { topic: "Cellular Respiration", score: 85, status: "strong" },
      { topic: "Database Normalization", score: 70, status: "moderate" },
      { topic: "CPU Scheduling", score: 40, status: "needs-improvement" }
    ],
    scoreTrend: [
      { date: "Aug 20", score: 72 },
      { date: "Aug 27", score: 80 },
      { date: "Sep 03", score: 75 },
      { date: "Sep 10", score: 88 },
      { date: "Sep 15", score: 79 }
    ]
  },

  // Personalized Recommendations
  recommendations: [
    {
      id: "rec-1",
      title: "Revise CPU Scheduling",
      actionText: "Start Revision",
      targetTab: "quiz",
      reason: "You scored 40% in your previous quiz on this topic.",
      category: "Urgent Review",
      badgeType: "danger"
    },
    {
      id: "rec-2",
      title: "Review Step-by-Step Explanation",
      actionText: "View Steps",
      targetTab: "steps",
      reason: "Step-by-step matches your preferred visual & procedural learning style.",
      category: "Preference Match",
      badgeType: "purple"
    },
    {
      id: "rec-3",
      title: "Practice More Flashcards on Tree Traversals",
      actionText: "Open Flashcards",
      targetTab: "flashcards",
      reason: "Active recall will solidify your binary search tree mastery before the next assessment.",
      category: "Active Recall",
      badgeType: "blue"
    },
    {
      id: "rec-4",
      title: "Review Simplified Notes for Quick Revision",
      actionText: "Read Notes",
      targetTab: "notes",
      reason: "It has been 16 days since you reviewed Database Normalization concepts.",
      category: "Spaced Repetition",
      badgeType: "warning"
    },
    {
      id: "rec-5",
      title: "Try a New Topic: Memory Management & Paging",
      actionText: "Generate Content",
      targetTab: "generator",
      reason: "Paging is the logical next progression after mastering CPU scheduling algorithms.",
      category: "Recommended Path",
      badgeType: "purple"
    }
  ]
};
