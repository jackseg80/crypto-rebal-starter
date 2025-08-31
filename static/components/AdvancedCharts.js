/**
 * Advanced Interactive Charts Component
 * Provides sophisticated charting capabilities for portfolio analytics
 */

class AdvancedCharts {
    constructor() {
        this.charts = new Map();
        this.themes = {
            dark: {
                background: '#1a1a1a',
                text: '#ffffff',
                grid: '#333333',
                accent: '#00ff88',
                warning: '#ffaa00',
                danger: '#ff4444'
            },
            light: {
                background: '#ffffff',
                text: '#333333', 
                grid: '#e0e0e0',
                accent: '#007acc',
                warning: '#ff8800',
                danger: '#cc0000'
            }
        };
        this.currentTheme = 'dark';
    }

    /**
     * Create portfolio composition pie chart with drill-down
     */
    createPortfolioComposition(containerId, data, options = {}) {
        const container = document.getElementById(containerId);
        const theme = this.themes[this.currentTheme];
        
        // Prepare data for nested pie chart
        const formattedData = data.map(item => ({
            name: item.symbol,
            y: item.percentage,
            value: item.value_usd,
            color: this.getAssetColor(item.symbol),
            drilldown: item.symbol.toLowerCase()
        }));

        const config = {
            chart: {
                type: 'pie',
                backgroundColor: theme.background,
                style: {
                    fontFamily: 'Inter, system-ui, sans-serif'
                },
                height: options.height || 400
            },
            title: {
                text: options.title || 'Portfolio Composition',
                style: { color: theme.text, fontSize: '18px', fontWeight: '600' }
            },
            tooltip: {
                backgroundColor: theme.background,
                borderColor: theme.grid,
                style: { color: theme.text },
                formatter: function() {
                    return `
                        <b>${this.point.name}</b><br/>
                        <span style="color:${this.point.color}">●</span> 
                        ${this.y.toFixed(2)}% ($${this.point.value.toLocaleString()})
                    `;
                }
            },
            plotOptions: {
                pie: {
                    allowPointSelect: true,
                    cursor: 'pointer',
                    dataLabels: {
                        enabled: true,
                        format: '<b>{point.name}</b><br>{point.percentage:.1f}%',
                        style: { color: theme.text, textOutline: 'none' }
                    },
                    showInLegend: true,
                    innerSize: options.innerSize || '40%',
                    depth: 45,
                    states: {
                        hover: {
                            halo: {
                                size: 10,
                                opacity: 0.25
                            }
                        }
                    }
                }
            },
            legend: {
                itemStyle: { color: theme.text },
                itemHoverStyle: { color: theme.accent }
            },
            series: [{
                name: 'Portfolio',
                colorByPoint: true,
                data: formattedData,
                point: {
                    events: {
                        click: function(e) {
                            if (options.onAssetClick) {
                                options.onAssetClick(this.name, this);
                            }
                        }
                    }
                }
            }],
            credits: { enabled: false },
            exporting: {
                enabled: true,
                buttons: {
                    contextButton: {
                        theme: { fill: theme.background, stroke: theme.grid }
                    }
                }
            }
        };

        const chart = Highcharts.chart(containerId, config);
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create multi-series price performance chart
     */
    createPerformanceChart(containerId, assets, priceData, options = {}) {
        const theme = this.themes[this.currentTheme];
        
        // Prepare series data
        const series = assets.map((asset, index) => ({
            name: asset,
            data: priceData[asset]?.map(point => [
                new Date(point.timestamp).getTime(),
                point.normalized_price || point.price
            ]) || [],
            color: this.getAssetColor(asset),
            lineWidth: 2,
            marker: {
                enabled: false,
                states: {
                    hover: { enabled: true, radius: 4 }
                }
            },
            visible: index < 10, // Show max 10 series by default
            events: {
                legendItemClick: function(e) {
                    // Custom legend behavior
                    return true;
                }
            }
        }));

        const config = {
            chart: {
                type: 'spline',
                backgroundColor: theme.background,
                zoomType: 'xy',
                height: options.height || 500,
                style: { fontFamily: 'Inter, system-ui, sans-serif' }
            },
            title: {
                text: options.title || 'Asset Performance Comparison',
                style: { color: theme.text, fontSize: '18px', fontWeight: '600' }
            },
            subtitle: {
                text: 'Click and drag to zoom • Click legend to show/hide assets',
                style: { color: theme.text, opacity: 0.7 }
            },
            xAxis: {
                type: 'datetime',
                gridLineColor: theme.grid,
                labels: { style: { color: theme.text } },
                crosshair: {
                    width: 1,
                    color: theme.accent,
                    dashStyle: 'shortdot'
                }
            },
            yAxis: {
                title: {
                    text: 'Normalized Price (%)',
                    style: { color: theme.text }
                },
                gridLineColor: theme.grid,
                labels: { 
                    style: { color: theme.text },
                    formatter: function() {
                        return this.value.toFixed(1) + '%';
                    }
                },
                plotLines: [{
                    value: 0,
                    color: theme.text,
                    width: 1,
                    dashStyle: 'dash'
                }]
            },
            tooltip: {
                backgroundColor: theme.background,
                borderColor: theme.grid,
                style: { color: theme.text },
                shared: true,
                crosshairs: true,
                formatter: function() {
                    let html = `<b>${new Date(this.x).toLocaleDateString()}</b><br/>`;
                    this.points.forEach(point => {
                        html += `<span style="color:${point.color}">●</span> `;
                        html += `${point.series.name}: ${point.y.toFixed(2)}%<br/>`;
                    });
                    return html;
                }
            },
            legend: {
                enabled: true,
                maxHeight: 100,
                itemStyle: { color: theme.text },
                itemHoverStyle: { color: theme.accent },
                navigation: {
                    activeColor: theme.accent,
                    inactiveColor: theme.grid
                }
            },
            plotOptions: {
                spline: {
                    animation: {
                        duration: 1000
                    },
                    marker: {
                        enabled: false,
                        symbol: 'circle'
                    },
                    lineWidth: 2,
                    states: {
                        hover: {
                            lineWidth: 3
                        }
                    }
                }
            },
            series: series,
            credits: { enabled: false },
            exporting: {
                enabled: true,
                buttons: {
                    contextButton: {
                        theme: { fill: theme.background, stroke: theme.grid }
                    }
                }
            },
            responsive: {
                rules: [{
                    condition: {
                        maxWidth: 500
                    },
                    chartOptions: {
                        legend: {
                            enabled: false
                        },
                        yAxis: {
                            labels: {
                                align: 'left',
                                x: 0,
                                y: -2
                            },
                            title: {
                                text: null
                            }
                        }
                    }
                }]
            }
        };

        const chart = Highcharts.chart(containerId, config);
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create correlation heatmap
     */
    createCorrelationHeatmap(containerId, correlationMatrix, assets, options = {}) {
        const theme = this.themes[this.currentTheme];
        
        // Convert correlation matrix to Highcharts format
        const data = [];
        for (let i = 0; i < assets.length; i++) {
            for (let j = 0; j < assets.length; j++) {
                data.push([j, i, correlationMatrix[i][j]]);
            }
        }

        const config = {
            chart: {
                type: 'heatmap',
                backgroundColor: theme.background,
                height: Math.max(400, assets.length * 25),
                marginTop: 40,
                marginBottom: 80
            },
            title: {
                text: options.title || 'Asset Correlation Matrix',
                style: { color: theme.text, fontSize: '18px', fontWeight: '600' }
            },
            xAxis: {
                categories: assets,
                labels: {
                    rotation: -45,
                    style: { color: theme.text, fontSize: '11px' }
                }
            },
            yAxis: {
                categories: assets,
                title: null,
                labels: {
                    style: { color: theme.text, fontSize: '11px' }
                }
            },
            colorAxis: {
                min: -1,
                max: 1,
                stops: [
                    [0, '#ff4444'],      // Strong negative correlation
                    [0.25, '#ffaa44'],   // Weak negative correlation  
                    [0.5, '#ffffff'],    // No correlation
                    [0.75, '#44aaff'],   // Weak positive correlation
                    [1, '#44ff44']       // Strong positive correlation
                ],
                labels: {
                    style: { color: theme.text }
                }
            },
            legend: {
                align: 'right',
                layout: 'vertical',
                margin: 0,
                verticalAlign: 'top',
                y: 25,
                symbolHeight: 280,
                itemStyle: { color: theme.text }
            },
            tooltip: {
                backgroundColor: theme.background,
                borderColor: theme.grid,
                style: { color: theme.text },
                formatter: function() {
                    const correlation = this.point.value;
                    const strength = Math.abs(correlation);
                    let description;
                    if (strength > 0.7) description = 'Strong';
                    else if (strength > 0.3) description = 'Moderate';
                    else description = 'Weak';
                    
                    const direction = correlation > 0 ? 'Positive' : 'Negative';
                    
                    return `
                        <b>${assets[this.point.y]} vs ${assets[this.point.x]}</b><br/>
                        Correlation: ${correlation.toFixed(3)}<br/>
                        <em>${description} ${direction}</em>
                    `;
                }
            },
            series: [{
                name: 'Correlation',
                borderWidth: 1,
                borderColor: theme.grid,
                data: data,
                dataLabels: {
                    enabled: true,
                    color: theme.text,
                    formatter: function() {
                        return this.point.value.toFixed(2);
                    },
                    style: {
                        fontSize: '10px',
                        textOutline: 'none'
                    }
                }
            }],
            credits: { enabled: false },
            exporting: {
                enabled: true,
                buttons: {
                    contextButton: {
                        theme: { fill: theme.background, stroke: theme.grid }
                    }
                }
            }
        };

        const chart = Highcharts.chart(containerId, config);
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Create risk/return scatter plot
     */
    createRiskReturnScatter(containerId, assets, riskReturnData, options = {}) {
        const theme = this.themes[this.currentTheme];
        
        const data = assets.map(asset => {
            const assetData = riskReturnData[asset] || {};
            return {
                name: asset,
                x: assetData.volatility || 0, // Risk (x-axis)
                y: assetData.return || 0,     // Return (y-axis)
                z: assetData.sharpe || 0,     // Bubble size based on Sharpe
                color: this.getAssetColor(asset),
                marker: {
                    fillOpacity: 0.7,
                    lineWidth: 2,
                    lineColor: theme.text
                }
            };
        });

        const config = {
            chart: {
                type: 'bubble',
                backgroundColor: theme.background,
                height: options.height || 500,
                zoomType: 'xy'
            },
            title: {
                text: options.title || 'Risk vs Return Analysis',
                style: { color: theme.text, fontSize: '18px', fontWeight: '600' }
            },
            subtitle: {
                text: 'Bubble size represents Sharpe ratio',
                style: { color: theme.text, opacity: 0.7 }
            },
            xAxis: {
                title: {
                    text: 'Risk (Volatility %)',
                    style: { color: theme.text }
                },
                gridLineColor: theme.grid,
                labels: { 
                    style: { color: theme.text },
                    formatter: function() {
                        return this.value.toFixed(1) + '%';
                    }
                }
            },
            yAxis: {
                title: {
                    text: 'Expected Return %',
                    style: { color: theme.text }
                },
                gridLineColor: theme.grid,
                labels: { 
                    style: { color: theme.text },
                    formatter: function() {
                        return this.value.toFixed(1) + '%';
                    }
                },
                plotLines: [{
                    value: 0,
                    color: theme.text,
                    width: 1,
                    dashStyle: 'dash'
                }]
            },
            tooltip: {
                backgroundColor: theme.background,
                borderColor: theme.grid,
                style: { color: theme.text },
                useHTML: true,
                formatter: function() {
                    return `
                        <div style="text-align: center;">
                            <b>${this.point.name}</b><br/>
                            <span style="color:${this.point.color}">●</span>
                            Risk: ${this.point.x.toFixed(2)}%<br/>
                            Return: ${this.point.y.toFixed(2)}%<br/>
                            Sharpe: ${this.point.z.toFixed(3)}
                        </div>
                    `;
                }
            },
            plotOptions: {
                bubble: {
                    minSize: 10,
                    maxSize: 50,
                    zMin: -2,
                    zMax: 3,
                    dataLabels: {
                        enabled: true,
                        format: '{point.name}',
                        style: { 
                            color: theme.text,
                            textOutline: '1px contrast',
                            fontSize: '10px'
                        }
                    }
                }
            },
            legend: {
                enabled: false
            },
            series: [{
                name: 'Assets',
                data: data,
                point: {
                    events: {
                        click: function(e) {
                            if (options.onAssetClick) {
                                options.onAssetClick(this.name, this);
                            }
                        }
                    }
                }
            }],
            credits: { enabled: false },
            exporting: {
                enabled: true,
                buttons: {
                    contextButton: {
                        theme: { fill: theme.background, stroke: theme.grid }
                    }
                }
            }
        };

        const chart = Highcharts.chart(containerId, config);
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * Get consistent color for asset
     */
    getAssetColor(symbol) {
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
            '#F8C471', '#82E0AA', '#F1948A', '#85929E', '#A569BD',
            '#5DADE2', '#58D68D', '#F4D03F', '#EB984E', '#AED6F1'
        ];
        
        // Generate consistent hash-based index
        let hash = 0;
        for (let i = 0; i < symbol.length; i++) {
            const char = symbol.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        
        return colors[Math.abs(hash) % colors.length];
    }

    /**
     * Switch between light/dark themes
     */
    switchTheme(themeName = 'dark') {
        this.currentTheme = themeName;
        
        // Update all existing charts
        this.charts.forEach((chart, containerId) => {
            if (chart && !chart.renderer.forExport) {
                chart.destroy();
                // Re-render would need the original data - store this in chart options
            }
        });
    }

    /**
     * Destroy all charts
     */
    destroyAll() {
        this.charts.forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts.clear();
    }

    /**
     * Resize chart to fit container
     */
    resize(containerId) {
        const chart = this.charts.get(containerId);
        if (chart && chart.reflow) {
            chart.reflow();
        }
    }

    /**
     * Export chart as image
     */
    exportChart(containerId, format = 'png', filename = 'chart') {
        const chart = this.charts.get(containerId);
        if (chart && chart.exportChart) {
            chart.exportChart({
                type: `image/${format}`,
                filename: filename,
                sourceWidth: 1200,
                sourceHeight: 600
            });
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdvancedCharts;
} else if (typeof window !== 'undefined') {
    window.AdvancedCharts = AdvancedCharts;
}