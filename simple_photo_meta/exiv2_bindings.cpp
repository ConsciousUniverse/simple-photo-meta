#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <exiv2/exiv2.hpp>
#include <string>
#include <memory>
#include <map>
#include <vector>
#include <set>

namespace py = pybind11;

// Map human-readable IPTC labels to raw Exiv2 keys
static const std::map<std::string, std::string> humanToRawKey = {
    {"Caption", "Iptc.Application2.Caption"},
    {"Keywords", "Iptc.Application2.Keywords"},
    {"By-line", "Iptc.Application2.Byline"},
    {"By-lineTitle", "Iptc.Application2.BylineTitle"},
    {"DateCreated", "Iptc.Application2.DateCreated"},
    {"ObjectName", "Iptc.Application2.ObjectName"},
    {"Credit", "Iptc.Application2.Credit"},
    {"Source", "Iptc.Application2.Source"},
    {"CopyrightNotice", "Iptc.Application2.CopyrightNotice"},
    {"Headline", "Iptc.Application2.Headline"},
    {"SpecialInstructions", "Iptc.Application2.SpecialInstructions"},
    {"Category", "Iptc.Application2.Category"},
    {"SupplementalCategories", "Iptc.Application2.SupplementalCategories"},
    {"Urgency", "Iptc.Application2.Urgency"},
    {"City", "Iptc.Application2.City"},
    {"Province-State", "Iptc.Application2.Province-State"},
    {"Country-PrimaryLocationName", "Iptc.Application2.Country-PrimaryLocationName"},
    {"OriginalTransmissionReference", "Iptc.Application2.OriginalTransmissionReference"},
    // Add more mappings as needed
};

class Exiv2Bind
{
public:
    Exiv2Bind(const std::string &path)
    {
        image_ = Exiv2::ImageFactory::open(path);
        if (!image_)
            throw std::runtime_error("Could not open image file: " + path);
        image_->readMetadata();
    }

    std::string getIptcTag(const std::string &key)
    {
        Exiv2::IptcData &data = image_->iptcData();
        auto pos = data.findKey(Exiv2::IptcKey(key));
        return (pos != data.end()) ? pos->toString() : std::string();
    }

    void setIptcTag(const std::string &key, const std::string &value)
    {
        Exiv2::IptcData &data = image_->iptcData();
        Exiv2::IptcKey iptcKey(key);
        auto val = std::unique_ptr<Exiv2::Value>(Exiv2::Value::create(Exiv2::TypeId::string));
        val->read(value);
        Exiv2::Iptcdatum datum(iptcKey, val.get());

        // Erase only matching entries
        auto it = data.findKey(iptcKey);
        while (it != data.end() && it->key() == key)
            it = data.erase(it);
        // Add new
        data.add(datum);
        // Save
        image_->setIptcData(data);
        image_->writeMetadata();
    }

    std::map<std::string, py::object> to_dict()
    {
        Exiv2::IptcData &data = image_->iptcData();
        std::set<std::string> uniqueKeys;
        for (auto const &md : data)
            uniqueKeys.insert(md.key());
        std::map<std::string, py::object> iptc;
        for (auto const &rawKey : uniqueKeys)
        {
            Exiv2::IptcKey iptcKey(rawKey);
            std::string label = iptcKey.tagName();
            if (label.empty())
                label = rawKey;

            // Collect values
            std::vector<std::string> values;
            auto it = data.findKey(iptcKey);
            while (it != data.end() && it->key() == rawKey)
            {
                values.push_back(it->toString());
                ++it;
            }

            // Deduplicate
            std::vector<std::string> uniq;
            std::set<std::string> seen;
            for (auto const &v : values)
                if (seen.insert(v).second)
                    uniq.push_back(v);

            // Multi vs single
            bool isMulti = (label == "Keywords");
            if (uniq.size() > 1 || isMulti)
            {
                iptc[label] = py::cast(uniq);
            }
            else if (!uniq.empty())
            {
                iptc[label] = py::cast(uniq.front());
            }
        }
        return {{"iptc", py::cast(iptc)}};
    }

    void from_dict(const std::map<std::string, py::object> &meta)
    {
        auto itSec = meta.find("iptc");
        if (itSec == meta.end())
            return;
        auto section = itSec->second.cast<std::map<std::string, py::object>>();
        Exiv2::IptcData &data = image_->iptcData();

        for (auto const &kv : section)
        {
            const auto &label = kv.first;
            const auto &valObj = kv.second;
            std::string rawKey;
            // 1) lookup in mapping
            auto itMap = humanToRawKey.find(label);
            if (itMap != humanToRawKey.end())
                rawKey = itMap->second;
            else
                continue; // unknown label, skip

            Exiv2::IptcKey iptcKey(rawKey);
            // Erase only matching entries
            auto it = data.findKey(iptcKey);
            while (it != data.end() && it->key() == rawKey)
                it = data.erase(it);

            // Add new
            if (py::isinstance<py::list>(valObj))
            {
                for (auto const &v : valObj.cast<py::list>())
                {
                    auto vs = v.cast<std::string>();
                    auto val = std::unique_ptr<Exiv2::Value>(Exiv2::Value::create(Exiv2::TypeId::string));
                    val->read(vs);
                    data.add(Exiv2::Iptcdatum(iptcKey, val.get()));
                }
            }
            else
            {
                auto vs = valObj.cast<std::string>();
                auto val = std::unique_ptr<Exiv2::Value>(Exiv2::Value::create(Exiv2::TypeId::string));
                val->read(vs);
                data.add(Exiv2::Iptcdatum(iptcKey, val.get()));
            }
        }
        // Save all changes without affecting other keys
        image_->setIptcData(data);
        image_->writeMetadata();
    }

private:
    std::unique_ptr<Exiv2::Image> image_;
};

PYBIND11_MODULE(exiv2bind, m)
{
    py::class_<Exiv2Bind>(m, "Exiv2Bind")
        .def(py::init<const std::string &>())
        .def("get_iptc_tag", &Exiv2Bind::getIptcTag)
        .def("set_iptc_tag", &Exiv2Bind::setIptcTag)
        .def("to_dict", &Exiv2Bind::to_dict)
        .def("from_dict", &Exiv2Bind::from_dict);
}
