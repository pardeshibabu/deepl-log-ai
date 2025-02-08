<?php

class LogAnalyzer {
    private $pythonPath;
    private $cliPath;

    public function __construct($pythonPath = 'python', $cliPath = 'app/cli/analyzer.py') {
        $this->pythonPath = $pythonPath;
        $this->cliPath = $cliPath;
    }

    public function analyzePrompt($prompt, $context = null, $outputFile = null) {
        $command = [
            $this->pythonPath,
            $this->cliPath,
            'analyze',
            '--prompt',
            escapeshellarg($prompt)
        ];

        if ($context) {
            $command[] = '--context';
            $command[] = escapeshellarg(json_encode($context));
        }

        if ($outputFile) {
            $command[] = '--output';
            $command[] = escapeshellarg($outputFile);
        }

        $output = [];
        $returnVar = 0;
        exec(implode(' ', $command), $output, $returnVar);

        if ($returnVar !== 0) {
            throw new Exception("Analysis failed with code: " . $returnVar);
        }

        return json_decode(implode("\n", $output), true);
    }

    public function getAnalysis($batchId, $outputFile = null) {
        $command = [
            $this->pythonPath,
            $this->cliPath,
            'get-analysis',
            $batchId
        ];

        if ($outputFile) {
            $command[] = '--output';
            $command[] = escapeshellarg($outputFile);
        }

        $output = [];
        $returnVar = 0;
        exec(implode(' ', $command), $output, $returnVar);

        if ($returnVar !== 0) {
            throw new Exception("Failed to get analysis with code: " . $returnVar);
        }

        return json_decode(implode("\n", $output), true);
    }
}

// Usage example:
try {
    $analyzer = new LogAnalyzer();
    
    // Analyze a prompt
    $result = $analyzer->analyzePrompt(
        "Analyze this database connection error",
        ["error_message" => "Connection refused"]
    );
    print_r($result);

    // Get analysis results
    $analysis = $analyzer->getAnalysis("batch_id_here");
    print_r($analysis);
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
} 