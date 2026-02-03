import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ReadStructure, ReadSegment } from "@/types"

interface ReadStructureVisualizerProps {
    readStructure: ReadStructure | null
    className?: string
}

// Color mapping for segment types
const segmentColors: Record<string, string> = {
    barcode: "bg-blue-500",
    umi: "bg-purple-500",
    insert: "bg-green-500",
    linker: "bg-gray-400",
    polyT: "bg-yellow-500",
    index: "bg-orange-500",
    other: "bg-slate-500",
}

const segmentLabels: Record<string, string> = {
    barcode: "Barcode",
    umi: "UMI",
    insert: "Insert",
    linker: "Linker",
    polyT: "Poly-T",
    index: "Index",
    other: "Other",
}

export function ReadStructureVisualizer({
    readStructure,
    className,
}: ReadStructureVisualizerProps) {
    const [animationStep, setAnimationStep] = useState(0)
    const [isAnimating, setIsAnimating] = useState(true)

    // Animation effect
    useEffect(() => {
        if (!readStructure || !isAnimating) return

        const totalSegments = readStructure.segments.length
        if (animationStep >= totalSegments) {
            setIsAnimating(false)
            return
        }

        const timer = setTimeout(() => {
            setAnimationStep((prev) => prev + 1)
        }, 300) // 300ms per segment

        return () => clearTimeout(timer)
    }, [readStructure, animationStep, isAnimating])

    if (!readStructure) {
        return (
            <Card className={cn("", className)}>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Read Structure</CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-muted-foreground text-sm">
                        No read structure detected yet.
                    </p>
                </CardContent>
            </Card>
        )
    }

    // Group segments by read number
    const segmentsByRead: Record<number, ReadSegment[]> = {}
    readStructure.segments.forEach((seg) => {
        if (!segmentsByRead[seg.read_number]) {
            segmentsByRead[seg.read_number] = []
        }
        segmentsByRead[seg.read_number].push(seg)
    })

    // Sort reads
    const readNumbers = Object.keys(segmentsByRead)
        .map(Number)
        .sort((a, b) => a - b)

    // Calculate max length for scaling
    const maxLength = Math.max(
        readStructure.read1_length || 0,
        readStructure.read2_length || 0,
        150 // minimum scale
    )

    return (
        <Card className={cn("", className)}>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Read Structure</CardTitle>
                    <Badge variant="outline" className="text-xs">
                        {Math.round(readStructure.confidence * 100)}% confidence
                    </Badge>
                </div>
                <p className="text-muted-foreground text-sm">
                    {readStructure.assay_name}
                </p>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Feature badges */}
                <div className="flex gap-2 flex-wrap">
                    {readStructure.has_cell_barcode && (
                        <Badge className="bg-blue-500/20 text-blue-600 border-blue-500/30">
                            Cell Barcode
                        </Badge>
                    )}
                    {readStructure.has_umi && (
                        <Badge className="bg-purple-500/20 text-purple-600 border-purple-500/30">
                            UMI
                        </Badge>
                    )}
                    {readStructure.has_sample_barcode && (
                        <Badge className="bg-orange-500/20 text-orange-600 border-orange-500/30">
                            Sample Barcode
                        </Badge>
                    )}
                </div>

                {/* Read visualizations */}
                <div className="space-y-4">
                    {readNumbers.map((readNum) => {
                        const segments = segmentsByRead[readNum]
                        const readLength =
                            readNum === 1
                                ? readStructure.read1_length
                                : readNum === 2
                                    ? readStructure.read2_length
                                    : readNum === 3
                                        ? readStructure.index1_length
                                        : readStructure.index2_length

                        return (
                            <div key={readNum} className="space-y-1">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-muted-foreground w-16">
                                        {readNum <= 2 ? `Read ${readNum}` : `Index ${readNum - 2}`}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                        {readLength ? `${readLength}bp` : ""}
                                    </span>
                                </div>

                                {/* Segment bar */}
                                <div className="flex h-10 rounded-lg overflow-hidden border">
                                    {segments.map((segment, idx) => {
                                        const globalIdx = readStructure.segments.indexOf(segment)
                                        const isVisible = globalIdx < animationStep
                                        const widthPercent = (segment.length / maxLength) * 100

                                        return (
                                            <div
                                                key={idx}
                                                className={cn(
                                                    "flex items-center justify-center text-white text-xs font-medium transition-all duration-300 relative group",
                                                    segmentColors[segment.segment_type] || segmentColors.other,
                                                    isVisible
                                                        ? "opacity-100 scale-100"
                                                        : "opacity-0 scale-95"
                                                )}
                                                style={{
                                                    width: `${widthPercent}%`,
                                                    minWidth: segment.length > 5 ? "40px" : "20px",
                                                }}
                                            >
                                                <span className="truncate px-1">
                                                    {segment.length > 8 ? segment.name : segment.length + "bp"}
                                                </span>

                                                {/* Tooltip */}
                                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                                                    <div className="font-medium">{segment.name}</div>
                                                    <div>
                                                        {segment.start_position}-{segment.end_position} ({segment.length}bp)
                                                    </div>
                                                    {segment.description && (
                                                        <div className="text-muted-foreground">
                                                            {segment.description}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Legend */}
                <div className="flex flex-wrap gap-3 pt-2 border-t">
                    {Object.entries(segmentColors).map(([type, color]) => (
                        <div key={type} className="flex items-center gap-1.5">
                            <div className={cn("w-3 h-3 rounded", color)} />
                            <span className="text-xs text-muted-foreground">
                                {segmentLabels[type]}
                            </span>
                        </div>
                    ))}
                </div>

                {/* Detection notes */}
                {readStructure.detection_notes && (
                    <p className="text-xs text-muted-foreground border-t pt-2">
                        {readStructure.detection_notes}
                    </p>
                )}
            </CardContent>
        </Card>
    )
}
