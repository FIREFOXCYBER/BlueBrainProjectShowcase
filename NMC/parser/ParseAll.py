import os
from pyneuroml.neuron import export_to_neuroml2
from pyneuroml.neuron.nrn_export_utils import clear_neuron

from pyneuroml.lems import generate_lems_file_for_neuroml

from pyneuroml import pynml
import neuroml

from Biophysics import get_biophysical_properties

from jinja2 import Template

from neuroml import *
from neuron import *
from nrn import *
import json
import os.path



def parse_cell_info_file(cell_dir):
    
    cell_info_json = 'cellinfo.json'
    if os.path.isfile(cell_info_json):
        print("Reading cell info from: %s"%os.path.abspath(cell_info_json))
        with open(cell_info_json) as data_file:    
            data = json.load(data_file)

            return data
        
    else:
        data = {}
        e_type = ''
        e_type_info = cell_dir.split('_')[2]
        for c in e_type_info:
            if not c.isdigit(): 
                e_type+=c
        data['e-type'] = e_type
        
        return data

net_ref = "ManyCells"
net_doc = NeuroMLDocument(id=net_ref)

net = Network(id=net_ref)
net_doc.networks.append(net)

cell_dirs = []

cell_dirs = [ f for f in os.listdir('.') if (os.path.isdir(f) and os.path.isfile(f+'/.provenance.json')) ]

groups_info_file = 'groups.txt'

clear_neuron()
        
count = 0
for cell_dir in cell_dirs:
    
    print('------------------------------\n  Parsing %s'%cell_dir)
    
    if os.path.isdir(cell_dir):
        os.chdir(cell_dir)
    else:
        os.chdir('../'+cell_dir)

    bbp_ref = None
    
    template_file = open('template.hoc','r')
    for line in template_file:
        if line.startswith('begintemplate '):
            bbp_ref = line.split(' ')[1].strip()
            print(' > Assuming cell in directory %s is in a template named %s'%(cell_dir, bbp_ref))

    load_cell_file = 'loadcell.hoc'
    
    if not os.path.isfile(load_cell_file):
        
        print(' > No %s yet!!'%load_cell_file)
        
        variables = {}
        
        variables['cell'] = bbp_ref
        variables['groups_info_file'] = groups_info_file
        
        template = """
load_file("nrngui.hoc")

objref cvode
cvode = new CVode()
cvode.active(1)

//======================== settings ===================================

v_init = -80

hyp_amp = -0.062866
step_amp = 0.3112968
tstop = 3000

//=================== creating cell object ===========================
load_file("import3d.hoc")
objref cell

// Using 1 to force loading of the file, in case file with same name was loaded before...
load_file(1, "constants.hoc")
load_file(1, "morphology.hoc")
load_file(1, "biophysics.hoc")
load_file(1, "synapses/synapses.hoc")
load_file(1, "template.hoc")


cell = new {{ cell }}(0)
print "Created new cell using loadcell.hoc: {{ cell }}"

define_shape()

wopen("{{ groups_info_file }}")

fprint("//Saving information on groups in this cell...\\n")

fprint("- somatic\\n")
forsec {{ cell }}[0].somatic {
    fprint("%s\\n",secname())
}

fprint("- basal\\n")
forsec {{ cell }}[0].basal {
    fprint("%s\\n",secname())
}

fprint("- axonal\\n")
forsec {{ cell }}[0].axonal {
    fprint("%s\\n",secname())
}
fprint("- apical\\n")
forsec {{ cell }}[0].apical {
    fprint("%s\\n",secname())
}
wopen()
        """
        
        t = Template(template)

        contents = t.render(variables)

        load_cell = open(load_cell_file, 'w')
        load_cell.write(contents)
        load_cell.close()
        
        print(' > Written %s'%load_cell_file)
        
        
    if os.path.isfile(load_cell_file):
        
        cell_info = parse_cell_info_file(cell_dir)
        
        nml_file_name = "%s.net.nml"%bbp_ref
        nml_file_loc = "../../NeuroML2/%s"%nml_file_name
        
    
        export_to_neuroml2(load_cell_file, 
                           nml_file_loc, 
                           separateCellFiles=False,
                           includeBiophysicalProperties=False)
        
        print(' > Exported to: %s using %s'%(nml_file_loc, load_cell_file))
        
        nml_doc = pynml.read_neuroml2_file(nml_file_loc)
        
        cell = nml_doc.cells[0]
        
        print(' > Adding groups from: %s'%groups_info_file)
        groups = {}
        current_group = None
        for line in open(groups_info_file):
            if not line.startswith('//'):
                if line.startswith('- '):
                    current_group = line[2:-1]
                    print(' > Adding group: [%s]'%current_group)
                    groups[current_group] = []
                else:
                    section = line.split('.')[1].strip()
                    segment_group = section.replace('[','_').replace(']','')
                    groups[current_group].append(segment_group)
        
        for g in groups.keys():
            new_seg_group = neuroml.SegmentGroup(id=g)
            cell.morphology.segment_groups.append(new_seg_group)
            for sg in groups[g]:
                new_seg_group.includes.append(neuroml.Include(sg))
            
        bp, incl_chans = get_biophysical_properties(cell_info['e-type'], 
                                                    ignore_chans=['Ih', 'Ca_HVA', 'Ca_LVAst', 'Ca'],
                                                    templates_json="../templates.json")
        
        cell.biophysical_properties = bp
        
        notes = cell.notes
        notes+="\n\n****************************\n*\n*  This export to NeuroML2 has not yet been fully validated!!"+ \
            "\n*  Use with caution!!\n*\n****************************\n\n"
        cell.notes = notes
        for channel in incl_chans:
        
            nml_doc.includes.append(neuroml.IncludeType(
                                href="%s" % channel))
        
        pynml.write_neuroml2_file(nml_doc, nml_file_loc)
        
        
        generate_lems_file_for_neuroml(cell_dir,
                                       nml_file_loc,
                                       "network",
                                       3000,
                                       0.025,
                                       "LEMS_%s.xml"%cell_dir,
                                       '../../NeuroML2',
                                       copy_neuroml = False)
        
        pynml.nml2_to_svg(nml_file_loc)
        
        clear_neuron()
        
        net_doc.includes.append(IncludeType(nml_file_name))

        pop = Population(id="Pop_%s"%bbp_ref, component=bbp_ref+'_0_0', type="populationList")

        net.populations.append(pop)

        inst = Instance(id="0")
        pop.instances.append(inst)
        
        width = 6
        X = count%width
        Z = (count -X) / width
        inst.location = Location(x=300*X, y=0, z=300*Z)
        
        count+=1


net_file = '../../NeuroML2/'+net_ref+'.net.nml'
writers.NeuroMLWriter.write(net_doc, net_file)

print("Written network with %i cells in network to: %s"%(count,net_file))

pynml.nml2_to_svg(net_file)