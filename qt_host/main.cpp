#include <QApplication>
#include <QHeaderView>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTableWidget>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

class DmsWindow final : public QWidget {
    Q_OBJECT
public:
    DmsWindow() {
        setWindowTitle("DMS 上位机监控台");
        resize(920, 540);

        auto *layout = new QVBoxLayout(this);
        statusLabel_ = new QLabel("云端连接中...");
        table_ = new QTableWidget(0, 7);
        table_->setHorizontalHeaderLabels({"Time", "Device", "Level", "Code", "Score", "Latency", "Reason"});
        table_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);

        layout->addWidget(statusLabel_);
        layout->addWidget(table_);

        timer_ = new QTimer(this);
        connect(timer_, &QTimer::timeout, this, &DmsWindow::refreshData);
        timer_->start(1000);

        refreshData();
    }

private slots:
    void refreshData() {
        QNetworkRequest req(QUrl("http://127.0.0.1:8000/alerts?limit=30"));
        auto *reply = http_.get(req);
        connect(reply, &QNetworkReply::finished, this, [this, reply]() {
            if (reply->error() != QNetworkReply::NoError) {
                statusLabel_->setText("云端连接失败: " + reply->errorString());
                reply->deleteLater();
                return;
            }

            const auto doc = QJsonDocument::fromJson(reply->readAll());
            if (!doc.isArray()) {
                statusLabel_->setText("云端响应格式错误");
                reply->deleteLater();
                return;
            }

            const QJsonArray arr = doc.array();
            table_->setRowCount(arr.size());
            statusLabel_->setText(QString("最近告警: %1 条").arg(arr.size()));

            int row = 0;
            for (const auto &v : arr) {
                const auto obj = v.toObject();
                table_->setItem(row, 0, new QTableWidgetItem(QString::number(obj.value("ts_ms").toInt())));
                table_->setItem(row, 1, new QTableWidgetItem(obj.value("device_id").toString()));
                table_->setItem(row, 2, new QTableWidgetItem(obj.value("level").toString()));
                table_->setItem(row, 3, new QTableWidgetItem(obj.value("code").toString()));
                table_->setItem(row, 4, new QTableWidgetItem(QString::number(obj.value("score").toDouble(), 'f', 2)));
                table_->setItem(row, 5, new QTableWidgetItem(QString("%1ms").arg(obj.value("latency_ms").toInt())));
                table_->setItem(row, 6, new QTableWidgetItem(obj.value("reason").toString()));
                row++;
            }
            reply->deleteLater();
        });
    }

private:
    QLabel *statusLabel_ {nullptr};
    QTableWidget *table_ {nullptr};
    QTimer *timer_ {nullptr};
    QNetworkAccessManager http_;
};

#include "main.moc"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    DmsWindow w;
    w.show();
    return app.exec();
}
