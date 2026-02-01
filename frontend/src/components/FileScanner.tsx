import { FileText, FolderOpen, HardDrive, Database, Dna } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import type { ScanResult, FileMetadata, DirectoryMetadata, FileType } from "@/types"

interface FileScannerProps {
  scanResult: ScanResult | null
  isLoading: boolean
}

function getFileTypeVariant(fileType: FileType): "fastq" | "bam" | "cellranger" | "default" {
  switch (fileType) {
    case "fastq":
      return "fastq"
    case "bam":
    case "sam":
    case "cram":
      return "bam"
    case "cellranger_outs":
      return "cellranger"
    default:
      return "default"
  }
}

function getFileIcon(fileType: FileType) {
  switch (fileType) {
    case "fastq":
      return <Dna className="h-4 w-4" />
    case "bam":
    case "sam":
    case "cram":
      return <Database className="h-4 w-4" />
    case "cellranger_outs":
      return <FolderOpen className="h-4 w-4" />
    default:
      return <FileText className="h-4 w-4" />
  }
}

function FileItem({ file }: { file: FileMetadata }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="text-muted-foreground">
          {getFileIcon(file.file_type)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">{file.filename}</p>
          <p className="text-xs text-muted-foreground truncate">{file.parent_dir}</p>
        </div>
      </div>
      <div className="flex items-center gap-2 ml-2">
        {file.sample_name && (
          <Badge variant="outline" className="text-xs">
            {file.sample_name}
          </Badge>
        )}
        {file.read_number && (
          <Badge variant="secondary" className="text-xs">
            R{file.read_number}
          </Badge>
        )}
        <Badge variant={getFileTypeVariant(file.file_type)} className="text-xs uppercase">
          {file.file_type}
        </Badge>
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          {file.size_human}
        </span>
      </div>
    </div>
  )
}

function DirectoryItem({ dir }: { dir: DirectoryMetadata }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-cellranger/10 border border-cellranger/20 hover:bg-cellranger/15 transition-colors">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <FolderOpen className="h-4 w-4 text-cellranger" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{dir.name}</p>
          <p className="text-xs text-muted-foreground">
            {dir.file_count} files • {dir.total_size_human}
          </p>
        </div>
      </div>
      <Badge variant="cellranger" className="text-xs">
        {dir.dir_type}
      </Badge>
    </div>
  )
}

export function FileScanner({ scanResult, isLoading }: FileScannerProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Spinner size="lg" />
          <p className="mt-4 text-muted-foreground">Scanning directory for sequencing files...</p>
        </CardContent>
      </Card>
    )
  }

  if (!scanResult) {
    return null
  }

  const fastqFiles = scanResult.files.filter((f) => f.file_type === "fastq")
  const bamFiles = scanResult.files.filter((f) =>
    ["bam", "sam", "cram"].includes(f.file_type)
  )
  const otherFiles = scanResult.files.filter(
    (f) => !["fastq", "bam", "sam", "cram"].includes(f.file_type)
  )

  return (
    <div className="space-y-6">
      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5 text-primary" />
            Scan Summary
          </CardTitle>
          <CardDescription>
            Scanned: {scanResult.scan_path}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-muted/30">
              <p className="text-2xl font-bold text-foreground">{scanResult.total_files}</p>
              <p className="text-sm text-muted-foreground">Total Files</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-fastq/10 border border-fastq/20">
              <p className="text-2xl font-bold text-fastq">{scanResult.fastq_count}</p>
              <p className="text-sm text-muted-foreground">FASTQ Files</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-bam/10 border border-bam/20">
              <p className="text-2xl font-bold text-bam">{scanResult.bam_count}</p>
              <p className="text-sm text-muted-foreground">BAM Files</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-cellranger/10 border border-cellranger/20">
              <p className="text-2xl font-bold text-cellranger">{scanResult.cellranger_count}</p>
              <p className="text-sm text-muted-foreground">CellRanger</p>
            </div>
          </div>
          <p className="text-center mt-4 text-muted-foreground">
            Total size: <span className="font-medium text-foreground">{scanResult.total_size_human}</span>
          </p>
        </CardContent>
      </Card>

      {/* CellRanger Directories */}
      {scanResult.directories.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-cellranger" />
              CellRanger Outputs ({scanResult.directories.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {scanResult.directories.map((dir, i) => (
                <DirectoryItem key={i} dir={dir} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* FASTQ Files */}
      {fastqFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Dna className="h-4 w-4 text-fastq" />
              FASTQ Files ({fastqFiles.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {fastqFiles.map((file, i) => (
                <FileItem key={i} file={file} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* BAM Files */}
      {bamFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Database className="h-4 w-4 text-bam" />
              Alignment Files ({bamFiles.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {bamFiles.map((file, i) => (
                <FileItem key={i} file={file} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Other Files */}
      {otherFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Other Files ({otherFiles.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {otherFiles.map((file, i) => (
                <FileItem key={i} file={file} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
